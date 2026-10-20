"""Views de CRUD de candidatos (criar, excluir, detalhe, modal)."""

import logging
import threading

from django.db import Error as DBError
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from acesso.decorators import pode_editar, web_login_required, web_requer_tenant_context
from acesso.models import (
    ROLE_ADMIN_SAAS,
    ROLES_OFICIAIS,
    tenant_gprb,
    Usuario as _Usuario,
)
from acesso.session import obter_tenant_id, obter_usuario_sessao
from candidatos.models import Candidato, CandidatoObservacao

from .cache import invalidar_cache_kanban
from .emails import (
    _gerar_link_candidato,
    enviar_email_convite_async,
)

logger = logging.getLogger(__name__)


@web_login_required
@web_requer_tenant_context
def criar_candidato(request):
    """Cria um novo candidato em estágio 'Em análise' (Súplica)."""
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    papel = request.session.get('usuario', {}).get('role')
    if papel not in ('deputado_mestre', 'prefeito', 'admin_saas'):
        return JsonResponse({'erro': 'Sem permissão — a súplica só pode ser criada por Deputado, Prefeito ou Admin.'}, status=403)

    nome = request.POST.get('nome', '').strip()
    if not nome:
        return JsonResponse({'erros': ['Nome é obrigatório']}, status=400)

    prefeitura = request.POST.get('prefeitura', '').strip()
    loja = request.POST.get('loja', '').strip()
    if not prefeitura:
        return JsonResponse({'erros': ['Prefeitura é obrigatória']}, status=400)
    if not loja:
        return JsonResponse({'erros': ['Loja é obrigatória']}, status=400)

    cpf = request.POST.get('cpf', '').strip()
    email = request.POST.get('email', '').strip()
    celular = request.POST.get('celular', '').strip()

    tenant_id = obter_tenant_id(request)
    if not tenant_id:
        tenant = tenant_gprb()
        tenant_id = tenant.id if tenant else None

    if not tenant_id:
        return JsonResponse({'erros': ['Tenant não configurado']}, status=400)

    if cpf and Candidato.objects.filter(tenant_id=tenant_id, cpf=cpf).exists():
        return JsonResponse({'erros': ['Já existe um candidato com este CPF']}, status=400)

    usuario_sessao = obter_usuario_sessao(request)
    criador_id = usuario_sessao.get('id') if usuario_sessao else None

    from candidatos.oficialato import nivel_inicial_do_criador

    try:
        candidato = Candidato(
            tenant_id=tenant_id,
            nome_completo=nome,
            cpf=cpf,
            prefeitura=prefeitura,
            loja=loja,
            email=email,
            celular=celular,
            status=Candidato.Status.EM_ANALISE,
            revisao_atual=nivel_inicial_do_criador(papel),
            created_by_id=criador_id,
        )
        candidato.save()
    except IntegrityError:
        return JsonResponse({'erros': ['Já existe um candidato com este CPF']}, status=400)
    except DBError:
        logger.exception('Erro ao salvar candidato %r (tenant %s)', nome, tenant_id)
        return JsonResponse({'erros': ['Erro ao salvar o candidato']}, status=400)

    invalidar_cache_kanban(tenant_id)

    link = _gerar_link_candidato(request, candidato)
    email_enviado = False
    if candidato.email:
        logo_url = request.build_absolute_uri('/static/img/logow.webp')
        t = threading.Thread(
            target=enviar_email_convite_async,
            args=(request.get_host(), candidato.id, link, logo_url,
                  candidato.nome_completo, candidato.email),
            daemon=True,
        )
        t.start()
        email_enviado = True

    return JsonResponse({
        'ok': True,
        'candidato_id': candidato.id,
        'email_enviado': email_enviado,
        'mensagem': 'Candidato criado com sucesso!' + (' Convite sendo enviado por e-mail.' if email_enviado else ' (sem e-mail informado)'),
    })


@web_login_required
@web_requer_tenant_context
def excluir_candidato(request, pk):
    """Exclui um candidato (AJAX POST)."""
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)
    if not pode_editar(request):
        return JsonResponse({'erro': 'Sem permissão'}, status=403)

    tenant_id = obter_tenant_id(request)
    qs = Candidato.objects.filter(pk=pk)
    if tenant_id is not None:
        qs = qs.filter(tenant_id=tenant_id)

    candidato = qs.first()
    if candidato is None:
        return JsonResponse({'erro': 'Candidato não encontrado'}, status=404)

    papel = request.session.get('usuario', {}).get('role')
    from candidatos.oficialato import pode_ver_candidato
    if not pode_ver_candidato(candidato.revisao_atual, papel):
        return JsonResponse({'erro': 'Sem permissão — candidato fora da sua fase.'}, status=403)

    candidato.delete()
    invalidar_cache_kanban(tenant_id)
    return JsonResponse({'ok': True})


@web_login_required
def candidato_detalhe(request, pk):
    """Detalhe do candidato (Súplica) — exibe dados e estado da revisão."""
    if request.method != 'GET':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    papel = request.session.get('usuario', {}).get('role')
    if papel not in (ROLES_OFICIAIS + (ROLE_ADMIN_SAAS,)):
        return JsonResponse({'erro': 'Sem permissão'}, status=403)

    candidato = get_object_or_404(
        Candidato.objects.select_related('created_by'),
        pk=pk,
    )
    if candidato.tenant_id != obter_tenant_id(request) and papel != ROLE_ADMIN_SAAS:
        return JsonResponse({'erro': 'Candidato não pertence ao tenant'}, status=403)

    from candidatos.oficialato import pode_ver_candidato
    if not pode_ver_candidato(candidato.revisao_atual, papel):
        return JsonResponse({'erro': 'Sem permissão — candidato fora da sua fase.'}, status=403)

    if not _candidato_pode_visualizar(candidato):
        return JsonResponse({'erro': 'Ficha ainda não enviada'}, status=404)

    return render(request, 'candidatos/detalhe.html', {
        'candidato': candidato,
    })


def _candidato_pode_visualizar(candidato):
    """True quando o candidato já enviou a ficha."""
    return candidato.token_used_at is not None or candidato.status in (
        Candidato.Status.EM_REVISAO,
        Candidato.Status.APROVADO,
        Candidato.Status.INICIADO,
    )


@web_login_required
def candidato_modal_detalhe(request, pk):
    """Retorna dados do candidato para o modal de detalhe no kanban."""
    if request.method != 'GET':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    papel = request.session.get('usuario', {}).get('role')
    if papel not in (ROLES_OFICIAIS + (ROLE_ADMIN_SAAS,)):
        return JsonResponse({'erro': 'Sem permissão'}, status=403)

    candidato = get_object_or_404(Candidato.objects.select_related('created_by'), pk=pk)

    if candidato.tenant_id != obter_tenant_id(request) and papel != ROLE_ADMIN_SAAS:
        return JsonResponse({'erro': 'Candidato não pertence ao tenant'}, status=403)

    from candidatos.oficialato import pode_ver_candidato
    if not pode_ver_candidato(candidato.revisao_atual, papel):
        return JsonResponse({'erro': 'Sem permissão — candidato fora da sua fase.'}, status=403)

    from recepcao.views.helpers import prefeitura_info as _prefeitura_info

    observacoes = CandidatoObservacao.objects.filter(candidato=candidato).order_by('-created_at')[:10]

    usuario = None
    uid = request.session.get('usuario_id')
    if uid:
        usuario = _Usuario.objects.filter(pk=uid).first()

    from candidatos.oficialato import (
        NIVEL_PARA_PAPEL_ACAO,
        pode_atuar_na_vez,
    )

    nivel = candidato.revisao_atual
    pode_observar = True
    pode_aprovar = pode_atuar_na_vez(candidato, usuario, papel) or papel == 'admin_saas'
    pode_devolver = pode_atuar_na_vez(candidato, usuario, papel) or papel == 'admin_saas'
    pode_encaminhar = pode_atuar_na_vez(candidato, usuario, papel) or papel == 'admin_saas'
    na_vez = pode_atuar_na_vez(candidato, usuario, papel)
    oficial_vez = NIVEL_PARA_PAPEL_ACAO.get(nivel or Candidato.RevisaoAtual.DM, '')

    return JsonResponse({
        'ok': True,
        'candidato': {
            'id': candidato.id,
            'nome_completo': candidato.nome_completo,
            'cpf': candidato.cpf,
            'email': candidato.email,
            'celular': candidato.celular,
            'prefeitura': _prefeitura_info(candidato.prefeitura)['nome'] or '—',
            'loja': candidato.loja,
            'status': candidato.status,
            'status_label': candidato.get_status_display(),
            'status_cor': candidato.COR_STATUS_KANBAN.get(candidato.status, '#94a3b8'),
            'revisao_atual': candidato.revisao_atual or '',
            'revisao_label': candidato.get_revisaocurrent_display if candidato.revisao_atual else '',
            'foto_url': candidato.foto.url if candidato.foto else '',
            'data_nascimento': candidato.data_nascimento.isoformat() if candidato.data_nascimento else '',
            'created_at': candidato.created_at.isoformat() if candidato.created_at else '',
            'data_aprovacao': candidato.data_aprovacao.isoformat() if candidato.data_aprovacao else '',
        },
        'observacoes': [{
            'autor_nome': o.autor_nome,
            'autor_papel': o.autor_papel,
            'texto': o.texto,
            'created_at': o.created_at.isoformat() if o.created_at else '',
        } for o in observacoes],
        'pode_observar': pode_observar,
        'pode_aprovar': pode_aprovar,
        'pode_devolver': pode_devolver,
        'pode_encaminhar': pode_encaminhar,
        'na_vez': na_vez,
        'oficial_vez': oficial_vez,
        'revisao_atual': nivel,
        'revisao_label': candidato.get_revisaocurrent_display if nivel else '',
        'criador_nome': candidato.created_by.nome if candidato.created_by_id else '',
    })
