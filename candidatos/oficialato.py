"""
Service layer para o fluxo de preliminaries do oficialato (deputado → suplica).

Este módulo centraliza a lógica de negócio pura (sem HTTP) do workflow de
7 níveis do PRD-SPRINT; a camada de views chama as funções aqui e trata
apenas pontos de entrada (redirect, JSON, templates).

As transições são atômicas e validam:
- permissão por papel versus nível atual do candidato;
- ordem correta das etapas;
- ausência de duplicidade de CPF;
- CPF + data_nascimento presentes na transformação em membro.
"""

import logging

from django.db import IntegrityError, transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import (
    Candidato,
    CandidatoObservacao,
)
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import Error as DBError

logger = logging.getLogger(__name__)


def _author_slug(papel):
    return {
        'sys_admin': 'sys_admin',
        'deputado_mestre': 'DM',
        'prefeito': 'PREFEITO',
        'grande_tesoureiro': 'TESOUREIRO',
        'grande_chanceler': 'CHANCELER',
        'grande_prior': 'PRIOR',
    }.get(papel, papel)


def _author_label(papel):
    return {
        'sys_admin': 'SYS_ADMIN',
        'deputado_mestre': 'Delegado Mestre',
        'prefeito': 'Prefeito',
        'grande_tesoureiro': 'Grande Tesoureiro',
        'grande_chanceler': 'Grande Chanceler',
        'grande_prior': 'Grão Prior',
    }.get(papel, papel)


PAPEL_PARA_NIVEL = {
    'deputado_mestre': Candidato.RevisaoAtual.DM,
    'prefeito': Candidato.RevisaoAtual.PREFEITO,
    'grande_tesoureiro': Candidato.RevisaoAtual.TESOUREIRO,
    'grande_chanceler': Candidato.RevisaoAtual.CHANCELER,
    'grande_prior': Candidato.RevisaoAtual.PRIOR,
}

NIVEL_PARA_PAPEL = {v: k for k, v in PAPEL_PARA_NIVEL.items()}

ORDEM_REVISAO = [
    Candidato.RevisaoAtual.DM,
    Candidato.RevisaoAtual.PREFEITO,
    Candidato.RevisaoAtual.TESOUREIRO,
    Candidato.RevisaoAtual.CHANCELER,
    Candidato.RevisaoAtual.PRIOR,
    Candidato.RevisaoAtual.CHANCELER_2,
    Candidato.RevisaoAtual.DM_FINAL,
]

NIVEL_INDEX = {n: i for i, n in enumerate(ORDEM_REVISAO)}


# Cadeia de revisão onde CADA NÍVEL tem um oficial responsável por agir.
# (DM_FINAL/CHANCELER_2 existem no modelo como níveis internos do PRD; a cadeia
# operacional de encaminhar/devolver anda por estes 5 papéis.)
CADEIA_ACAO = [
    Candidato.RevisaoAtual.DM,
    Candidato.RevisaoAtual.PREFEITO,
    Candidato.RevisaoAtual.TESOUREIRO,
    Candidato.RevisaoAtual.CHANCELER,
    Candidato.RevisaoAtual.PRIOR,
]

NIVEL_PARA_PAPEL_ACAO = {
    Candidato.RevisaoAtual.DM: 'deputado_mestre',
    Candidato.RevisaoAtual.PREFEITO: 'prefeito',
    Candidato.RevisaoAtual.TESOUREIRO: 'grande_tesoureiro',
    Candidato.RevisaoAtual.CHANCELER: 'grande_chanceler',
    Candidato.RevisaoAtual.PRIOR: 'grande_prior',
}
IDX_CADEIA = {n: i for i, n in enumerate(CADEIA_ACAO)}

# Coluna do kanban de recepção em que o card do candidato aparece, por nível
# de revisão (DM/vazio fica na coluna 'suplica').
NIVEL_PARA_COLUNA_KANBAN = {
    Candidato.RevisaoAtual.PREFEITO: 'prefeito',
    Candidato.RevisaoAtual.TESOUREIRO: 'tesoureiro',
    Candidato.RevisaoAtual.CHANCELER: 'chanceler_i',
    Candidato.RevisaoAtual.PRIOR: 'grao_prior',
    Candidato.RevisaoAtual.CHANCELER_2: 'chanceler_ii',
    Candidato.RevisaoAtual.DM_FINAL: 'deputado_ii',
    # Candidato aprovado (em revisão concluída) — vai para a coluna de prefeitura
    # quando está no nível do Prefeito, ou para a coluna do próximo oficial
    # quando já foi encaminhado adiante. Sem revisão definida, prefeito por padrão.
    Candidato.Status.APROVADO: 'prefeito',
}


def pode_ver_candidato(revisao_atual, papel):
    """Visibilidade do candidato para o papel no CRM.

    - Admin: acesso total.
    - Fase Súplica (nível DM/vazio): todo o oficialato enxerga.
    - Depois que o Delegado aprova e encaminha (nível >= PREFEITO): o
      Delegado perde o acesso — só o Prefeito, o oficial dono do nível
      atual (mais adiante na cadeia) e o Admin continuam com acesso.
    """
    if papel == 'admin_saas':
        return True
    nivel = revisao_atual or Candidato.RevisaoAtual.DM
    if nivel == Candidato.RevisaoAtual.DM:
        return True
    return NIVEL_PARA_PAPEL_ACAO.get(nivel) == papel or papel == 'prefeito'

# Quem dá a aprovação DEFINITIVA (APROVADO). Os demais oficiais só encaminham
# adiante / devolvem ao nível anterior — nunca aprovam em definitivo.
ROLES_APROVACAO_FINAL = ('grande_prior', 'grande_chanceler', 'admin_saas')


# ---------------------------------------------------------------------------
# Permissões por "vez" (quem está com o candidato pode agir)
# ---------------------------------------------------------------------------

def _nivel_atual(candidato):
    return candidato.revisao_atual or Candidato.RevisaoAtual.DM


def pode_aprovar_final(papel):
    """Só Grão Prior, Grande Chanceler (e admin) aprovam em definitivo."""
    return papel in ROLES_APROVACAO_FINAL


def pode_atuar_na_vez(candidato, usuario, papel):
    """True quando `papel` é o oficial da vez do candidato.

    Regras:
    - admin_saas tem bypass total (visão global do sistema);
    - o papel tem que ser o dono do nível atual (revisao_atual);
    - enquanto o candidato está no nível do CRIADOR (DM), só o deputado que
      criou a súplica pode agir ("a aprovação da súplica só por quem a fez").
    """
    if papel == 'admin_saas':
        return True
    nivel = _nivel_atual(candidato)
    if NIVEL_PARA_PAPEL_ACAO.get(nivel) != papel:
        return False
    if nivel == Candidato.RevisaoAtual.DM and candidato.created_by_id is not None:
        if usuario is None or getattr(usuario, 'id', None) is None:
            return False
        return int(usuario.id) == int(candidato.created_by_id)
    return True


def pode_encaminhar(candidato, usuario, papel):
    """Avança 1 nível na cadeia — só o oficial da vez (status em revisão)."""
    if not pode_atuar_na_vez(candidato, usuario, papel):
        return False
    if candidato.status != Candidato.Status.EM_REVISAO:
        return False
    nivel = _nivel_atual(candidato)
    if nivel not in IDX_CADEIA:
        return False
    # Grão Prior é o fim da cadeia: daqui em diante é aprovação final.
    return IDX_CADEIA[nivel] < len(CADEIA_ACAO) - 1


def pode_devolver(candidato, usuario, papel):
    """Recua 1 nível (ex.: Prefeito devolve ao Deputado) — só o oficial da vez."""
    if not pode_atuar_na_vez(candidato, usuario, papel):
        return False
    if candidato.status != Candidato.Status.EM_REVISAO:
        return False
    nivel = _nivel_atual(candidato)
    if nivel not in IDX_CADEIA:
        return False
    return IDX_CADEIA[nivel] > 0


def pode_aprovar_agora(candidato, usuario, papel):
    """Botão Aprovar: aprovação DEFINITIVA (Grão Prior / Grande Chanceler / Admin).

    O candidato precisa ter chegado no nível do aprovador (Grão Prior só aprova
    quando está com ele; idem Grande Chanceler). Admin tem bypass total.
    """
    if not pode_aprovar_final(papel):
        return False
    if candidato.status != Candidato.Status.EM_REVISAO:
        return False
    if papel == 'admin_saas':
        return True
    return NIVEL_PARA_PAPEL_ACAO.get(_nivel_atual(candidato)) == papel


def _obs(candidato, papel, autor_nome, texto):
    """Registra uma observação acumulativa: novo texto empilha em cima do anterior,
    mas sem repetir o último texto salvo (evita duplicação ao reabrir o modal).
    """
    # Pega a observação mais recente para decidir se há texto válido para empilhar
    anterior = CandidatoObservacao.objects.filter(
        candidato=candidato,
    ).exclude(
        texto__isnull=True,
    ).order_by('-created_at').first()

    # Só empilha se o texto novo for diferente do último salvo (evita duplicata)
    if anterior and anterior.texto and texto.strip() and texto.strip() != anterior.texto.strip():
        texto = texto + '\n\n' + anterior.texto

    return CandidatoObservacao.objects.create(
        candidato=candidato,
        autor_id=_author_slug(papel),
        autor_nome=autor_nome,
        autor_papel=_author_label(papel),
        texto=texto.strip() if texto else '',
    )


def aprovar_final(candidato, papel, autor_nome, observacao=''):
    """Aprovação DEFINITIVA (status → APROVADO)."""
    if not pode_aprovar_final(papel):
        return (False, candidato.status, _nivel_atual(candidato),
                'A aprovação final só pode ser feita pelo Grão Prior, Grande Chanceler ou Admin.')
    if candidato.status != Candidato.Status.EM_REVISAO:
        return (False, candidato.status, _nivel_atual(candidato),
                'Só é possível aprovar candidatos em revisão.')
    if candidato.status == Candidato.Status.APROVADO:
        return (True, candidato.status, _nivel_atual(candidato), None)

    with transaction.atomic():
        candidato.status = Candidato.Status.APROVADO
        candidato.data_aprovacao = timezone.now()
        candidato.save(update_fields=['status', 'data_aprovacao', 'updated_at'])
        _obs(candidato, papel, autor_nome, observacao or 'Aprovação final do candidato.')
    return (True, candidato.status, _nivel_atual(candidato), None)


def avancar_nivel(candidato,usuario, papel, autor_nome, observacao=''):
    """Encaminha para o PRÓXIMO oficial — quem está com o candidato aprova e passa adiante."""
    if not pode_encaminhar(candidato, usuario, papel):
        if candidato.status != Candidato.Status.EM_REVISAO:
            return (False, None, 'Candidato ainda não está em revisão.')
        return (False, None, 'Você não está com este candidato na vez — só o oficial responsável atual pode encaminhar.')

    if not observacao or not observacao.strip():
        return (False, None, 'Informe a observação desta aprovação/encaminhamento.')

    nivel_atual = _nivel_atual(candidato)
    idx = IDX_CADEIA[nivel_atual]
    proximo = CADEIA_ACAO[idx + 1]
    rotulo_proximo = NIVEL_PARA_PAPEL_ACAO[proximo]

    with transaction.atomic():
        candidato.revisao_atual = proximo
        candidato.save(update_fields=['revisao_atual', 'updated_at'])
        _obs(candidato, papel, autor_nome,
             observacao or f'Encaminhado para {_rotulo_papel(rotulo_proximo)}.')
    return (True, candidato.revisao_atual, None)


def devolver_nivel(candidato,usuario, papel, autor_nome, observacao=''):
    """Devolve para o oficial ANTERIOR (ex.: Prefeito devolve ao Deputado)."""
    if not pode_devolver(candidato, usuario, papel):
        return (False, None, 'Você não pode devolver este candidato agora.')

    if not observacao or not observacao.strip():
        return (False, None, 'Para devolver é obrigatório informar uma observação.')

    nivel_atual = _nivel_atual(candidato)
    idx = IDX_CADEIA[nivel_atual]
    anterior = CADEIA_ACAO[idx - 1]
    rotulo_anterior = NIVEL_PARA_PAPEL_ACAO[anterior]

    with transaction.atomic():
        candidato.revisao_atual = anterior
        candidato.save(update_fields=['revisao_atual', 'updated_at'])
        _obs(candidato, papel, autor_nome,
             observacao or f'Devolvido para {_rotulo_papel(rotulo_anterior)}.')
    return (True, candidato.revisao_atual, None)


def _rotulo_papel(papel):
    return {
        'deputado_mestre': 'o Deputado',
        'prefeito': 'o Prefeito',
        'grande_tesoureiro': 'o Tesoureiro',
        'grande_chanceler': 'o Chanceler',
        'grande_prior': 'o Grão Prior',
    }.get(papel, papel)


def nivel_inicial_do_criador(papel_criador):
    """Nível em que a súplica nasce — o criador (Deputado ou Prefeito) fica com ela."""
    if papel_criador == 'prefeito':
        return Candidato.RevisaoAtual.PREFEITO
    return Candidato.RevisaoAtual.DM


def _sessao_usuario(request):
    return request.session.get('usuario') or {}


def _sessao_papel(request):
    return _sessao_usuario(request).get('role') or ''


def _readonly_para_papel(request):
    papel = _sessao_papel(request)
    return papel in ('viewer',)


def _candidato_do_request(request, candidato_id):
    qs = Candidato.objects.all()
    if not request.session.get('usuario_id'):
        raise Http404('Acesso não autorizado')
    return get_object_or_404(qs, pk=candidato_id)


def _response_json(request, candidato, ok, mensagem):
    return JsonResponse({'ok': ok, 'mensagem': mensagem, 'candidato_id': candidato.id})


def aprovar_view(request, candidato_id):
    candidato = _candidato_do_request(request, candidato_id)
    papel = _sessao_papel(request)
    if papel not in ROLES_APROVACAO_FINAL:
        return _response_json(request, candidato, False, 'Sem permissão para aprovação final.')
    autor_nome = _sessao_usuario(request).get('nome') or 'Sistema'
    ok, _novo_status, _nivel, erro = aprovar_final(
        candidato, papel, autor_nome,
        observacao=request.POST.get('observacao', ''),
    )
    if not ok:
        return _response_json(request, candidato, False, erro)
    return _response_json(request, candidato, True, 'Candidato aprovado com sucesso.')


def avancar_nivel_captura_data(candidato, papel, autor_nome, observacao=''):
    """Same as avancar_nivel, but accepts (candidato, papel, autor_nome, observacao).
    Used by the UI 'Aprovar' button / api_aprovar_encaminhar."""
    # avancar_nivel expects (candidato, usuario, papel, autor_nome, observacao)
    return avancar_nivel(candidato, None, papel, autor_nome, observacao)

def devolver_nivel_captura_data(candidato, papel, autor_nome, observacao=''):
    """Devolve para o nível anterior e grava a data de devolução do nível atual.
    Used by the UI 'Devolver' button / api_devolver."""
    # devolver_nivel expects (candidato, usuario, papel, autor_nome, observacao)
    return devolver_nivel(candidato, None, papel, autor_nome, observacao)

def encaminhar_view(request, candidato_id):
    candidato = _candidato_do_request(request, candidato_id)
    papel = _sessao_papel(request)
    if _readonly_para_papel(request):
        return _response_json(request, candidato, False, 'Somente leitura.')
    autor_nome = _sessao_usuario(request).get('nome') or 'Sistema'
    ok, _nivel, erro = avancar_nivel(
        candidato, None, papel, autor_nome,
        observacao=request.POST.get('observacao', ''),
    )
    if not ok:
        return _response_json(request, candidato, False, erro)
    return _response_json(request, candidato, True, 'Encaminhado para próxima revisão.')


def devolver_view(request, candidato_id):
    candidato = _candidato_do_request(request, candidato_id)
    papel = _sessao_papel(request)
    if _readonly_para_papel(request):
        return _response_json(request, candidato, False, 'Somente leitura.')
    autor_nome = _sessao_usuario(request).get('nome') or 'Sistema'
    ok, _nivel, erro = devolver_nivel(
        candidato, None, papel, autor_nome,
        observacao=request.POST.get('observacao', ''),
    )
    if not ok:
        return _response_json(request, candidato, False, erro)
    return _response_json(request, candidato, True, 'Devolvido ao nível anterior.')


def iniciar_view(request, candidato_id):
    candidato = _candidato_do_request(request, candidato_id)
    papel = _sessao_papel(request)
    if papel not in ('deputado_mestre','prefeito','grande_tesoureiro','grande_chanceler','grande_prior','sys_admin'):
        return _response_json(request, candidato, False, 'Sem permissão para iniciar o candidato.')
    if candidato.status != Candidato.Status.APROVADO:
        return _response_json(request, candidato, False, 'Só é possível iniciar candidatos aprovados.')
    if not candidato.cpf:
        return _response_json(request, candidato, False, 'O candidato precisa ter CPF para ser iniciado.')
    if not candidato.data_nascimento:
        return _response_json(request, candidato, False, 'O candidato precisa ter data de nascimento para ser iniciado.')
    from acesso.decorators import tenant_id_da_sessao
    from acesso.models import Tenant
    tenant_id = tenant_id_da_sessao(request)
    if tenant_id is None:
        return _response_json(request, candidato, False, 'Tenant não configurado.')
    tenant = get_object_or_404(Tenant, pk=tenant_id)
    try:
        with transaction.atomic():
            Candidato.objects.create_member_from_candidato(candidato, tenant=tenant)
            candidato.status = Candidato.Status.INICIADO
            candidato.data_inicio = timezone.now()
            candidato.save(update_fields=['status', 'data_inicio', 'updated_at'])
        return _response_json(request, candidato, True, 'Candidato iniciado como membro.')
    except IntegrityError:
        logger.warning('Integridade ao iniciar candidato %s (tenant %s)', candidato_id, tenant_id)
        return _response_json(request, candidato, False, 'Já existe um membro com este CPF.')
    except (DBError, DjangoValidationError):
        logger.exception('Erro ao iniciar candidato %s', candidato_id)
        return _response_json(request, candidato, False, 'Erro ao iniciar o candidato.')
