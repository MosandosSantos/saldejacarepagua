"""Views para o módulo de Candidatos (Súplica)."""

import logging
import threading
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.mail import EmailMultiAlternatives
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from acesso.decorators import pode_editar, web_login_required
from acesso.models import (
    ROLE_ADMIN_SAAS,
    ROLE_DEPUTADO_MESTRE,
    ROLE_PREFEITO,
    ROLES_OFICIAIS,
)
from acesso.session import obter_tenant_id, obter_usuario_sessao

from .models import Candidato, CandidatoObservacao

logger = logging.getLogger(__name__)


def _gerar_link_candidato(request, candidato):
    """Gera link público para o candidato preencher a ficha."""
    if not candidato.access_token:
        candidato.generate_access_token()
        candidato.token_expires_at = timezone.now() + timedelta(days=7)
        candidato.save(update_fields=['access_token', 'token_expires_at', 'updated_at'])

    return request.build_absolute_uri(f'/candidato/{candidato.access_token}/')


def _enviar_email_candidato(request, candidato, link):
    """Envia e-mail HTML com convite gentil para o candidato preencher a ficha."""
    assunto = '✦ Convite — Candidatura ao Grande Priorado Retificado do Brasil'
    corpo_texto = f'''Prezado(a) {candidato.nome_completo},

É com grande honra que comunicamos o recebimento de sua indicação para integrar
os quadros do Grande Priorado Retificado do Brasil.

Acesse o link abaixo para preencher sua Ficha de Súplica:

{link}

Link válido por 7 dias · uso único.

Grande Priorado Retificado do Brasil — SAL do RER
'''
    corpo_html = render_to_string('candidatos/email_convite.html', {
        'nome': candidato.nome_completo.split()[0] if candidato.nome_completo else '',
        'link': link,
        'logo_url': request.build_absolute_uri('/static/img/gprbr.png'),
    })

    msg = EmailMultiAlternatives(
        assunto,
        corpo_texto,
        settings.DEFAULT_FROM_EMAIL,
        [candidato.email],
    )
    msg.attach_alternative(corpo_html, 'text/html')
    msg.send(fail_silently=False)


def _enviar_email_convite_async(request_host, candidato_id, link, logo_url, nome, email_destino):
    """Envia o e-mail de convite em background — não bloqueia a resposta HTTP (2-5s de SMTP)."""
    from django.conf import settings as _settings
    try:
        assunto = '✦ Convite — Candidatura ao Grande Priorado Retificado do Brasil'
        corpo_texto = f'''Prezado(a) {nome},

É com grande honra que comunicamos o recebimento de sua indicação para integrar
os quadros do Grande Priorado Retificado do Brasil.

Acesse o link abaixo para preencher sua Ficha de Súplica:

{link}

Link válido por 7 dias · uso único.

Grande Priorado Retificado do Brasil — SAL do RER
'''
        corpo_html = render_to_string('candidatos/email_convite.html', {
            'nome': nome.split()[0] if nome else '',
            'link': link,
            'logo_url': logo_url,
        })
        msg = EmailMultiAlternatives(
            assunto, corpo_texto, _settings.DEFAULT_FROM_EMAIL, [email_destino],
        )
        msg.attach_alternative(corpo_html, 'text/html')
        msg.send(fail_silently=False)

        # Confirma o envio: status → Convite (FICHA_ENVIADA). Só sobe de
        # EM_ANALISE — se o candidato já abriu a ficha (EM_PREENCHIMENTO),
        # o estado mais avançado prevalece (evita regressão na corrida).
        Candidato.objects.filter(
            pk=candidato_id, status=Candidato.Status.EM_ANALISE,
        ).update(status=Candidato.Status.FICHA_ENVIADA)
    except Exception:
        logger.exception('Falha ao enviar e-mail de convite (candidato %s)', candidato_id)


def candidato_dashboard(request, token):
    """Portal do candidato: status da sua candidatura (Súplica).

    Acesso público — autenticação via token de acesso (use único).
    mostra card com status, descrição, datas e atalho para terminar a súplica.
    """
    candidato = get_object_or_404(
        Candidato,
        access_token=token,
        token_expires_at__gt=timezone.now(),
    )
    if candidato.token_used_at:
        return render(request, 'candidatos/portal_dashboard.html', {
            'candidato': candidato,
            'token': token,
        })
    return render(request, 'candidatos/portal_dashboard.html', {
        'candidato': candidato,
        'token': token,
        'pode_editar': False,
    })


def candidato_suplica(request, token):
    """Portal do candidato: terminar a súplica (formulario completo + uploads).

    Bloqueia campos após envio. Exibe observações recebidas quando disponíveis.
    """
    get_object_or_404(
        Candidato,
        access_token=token,
        token_expires_at__gt=timezone.now(),
    )
    if request.method == 'POST':
        return candidato_formulario(request, token)
    return candidato_formulario(request, token)


@web_login_required
def criar_candidato(request):
    """Cria um novo candidato em estágio 'Em análise' (Súplica).

    A súplica pode ser criada pelo Deputado ou pelo Prefeito (admin tem bypass).
    O candidato nasce "com o criador" (revisao_atual = nível dele): a aprovação
    da ficha é só de quem a fez — outro deputado/prefeito não pode nem aprovar,
    nem devolver, nem editar.
    """
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    papel = request.session.get('usuario', {}).get('role')
    if papel not in (ROLE_DEPUTADO_MESTRE, ROLE_PREFEITO, ROLE_ADMIN_SAAS):
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

    # Obtém tenant da sessão (ou busca o tenant GPRB canônico como fallback).
    # IMPORTANTE: precisa ser o MESMO fallback do kanban (recepcao.views), senão
    # o candidato criado por admin_saas vai para um tenant e o funil exibe outro
    # — o candidato "some" logo após o cadastro.
    tenant_id = obter_tenant_id(request)
    if not tenant_id:
        from acesso.models import tenant_gprb
        tenant = tenant_gprb()
        tenant_id = tenant.id if tenant else None

    if not tenant_id:
        return JsonResponse({'erros': ['Tenant não configurado']}, status=400)

    if cpf and Candidato.objects.filter(tenant_id=tenant_id, cpf=cpf).exists():
        return JsonResponse({'erros': ['Já existe um candidato com este CPF']}, status=400)

    usuario_sessao = obter_usuario_sessao(request)
    criador_id = usuario_sessao.get('id') if usuario_sessao else None
    criador = None
    if criador_id:
        from acesso.models import Usuario as _Usuario
        criador = _Usuario.objects.filter(pk=criador_id).first()

    from .oficialato import nivel_inicial_do_criador

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
    except Exception as e:
        return JsonResponse({'erros': [f'Erro ao salvar: {e}']}, status=400)

    # Invalida cache do kanban para atualizar KPIs
    _invalidar_cache_kanban(tenant_id)

    # Gera token e envia e-mail em background (SMTP leva 2-5s — não bloqueia a resposta).
    # O status muda para FICHA_ENVIADA ("Convite") quando o envio conclui na thread.
    link = _gerar_link_candidato(request, candidato)
    email_enviado = False
    if candidato.email:
        logo_url = request.build_absolute_uri('/static/img/gprbr.png')
        t = threading.Thread(
            target=_enviar_email_convite_async,
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


def _invalidar_cache_kanban(tenant_id):
    """Invalida caches relacionados ao kanban.

    Limpa tanto o cache sem filtro quanto com filtros de prefeitura.
    """
    from django.core.cache import cache

    # Invalida cache de cards de candidatos (sem filtro e com filtros de prefeitura)
    # Como não sabemos todas as prefeituras possíveis, limpamos as chaves conhecidas
    # e também usamos a função de limpeza de cache do Django se disponível
    cache_keys_to_delete = [
        f'recepcao_cards_candidatos_{tenant_id}_30_todas',
        f'recepcao_cards_candidatos_{tenant_id}_50_todas',
        f'recepcao_cards_candidatos_{tenant_id}_30',
        f'recepcao_cards_candidatos_{tenant_id}_50',
    ]
    for key in cache_keys_to_delete:
        cache.delete(key)

    # Para chaves com prefeituras específicas, precisamos limpar todas as variações
    # Como o Django cache não suporta pattern matching, usamos uma abordagem diferente:
    # Incrementamos uma versão do cache que é usada nas chaves
    version_key = f'recepcao_cards_candidatos_version_{tenant_id}'
    current_version = cache.get(version_key, 0)
    cache.set(version_key, current_version + 1, timeout=3600)


@web_login_required
def api_prefeituras(request):
    """Retorna prefeituras GPRB em JSON (cache de 5 min — mudam raramente)."""
    from django.core.cache import cache

    try:
        from core.gprb import opcoes_prefeituras_usuario
        prefeituras = cache.get_or_set(
            'gprb:prefeituras', opcoes_prefeituras_usuario, 300,
        )
    except Exception:
        prefeituras = cache.get('gprb:prefeituras') or []
    return JsonResponse({'prefeituras': prefeituras})


@web_login_required
def api_lojas_por_prefeitura(request):
    """Retorna lojas GPRB de uma prefeitura em JSON (cache de 5 min por prefeitura)."""
    prefeitura_id = request.GET.get('prefeitura_id', '').strip()
    if not prefeitura_id:
        return JsonResponse({'lojas': []})

    from django.core.cache import cache

    # GPRB pode estar indisponível (conexão/banco) — o modal de Súplica depende
    # deste endpoint para liberar o select de Loja; em vez de 500, devolve lista
    # vazia como o api_prefeituras faz (o usuário vê mensagem no próprio modal).
    try:
        from core.gprb import connect

        # prefeitura_id pode ser o nome (novos cadastros) ou UUID (antigos) —
        # resolve para o ID real da prefeitura no banco GPRB
        conn = connect()
        try:
            cur = conn.cursor()
            cur.execute(
                'SELECT id FROM prefeitura WHERE id = %s OR nome = %s',
                (prefeitura_id, prefeitura_id),
            )
            row = cur.fetchone()
            if not row:
                return JsonResponse({'lojas': []})
            prefeitura_pk = row[0]
        finally:
            conn.close()

        cache_key = f'gprb:lojas:{prefeitura_pk}'
        lojas = cache.get(cache_key)
        if lojas is None:
            conn = connect()
            try:
                cur = conn.cursor()
                cur.execute(
                    'SELECT l.id, COALESCE(l."nomeFantasia", l."lojaMX", \'Loja \' || l.numero::text) '
                    'FROM loja l '
                    'WHERE l."prefeituraId" = %s AND l.situacao = %s '
                    'ORDER BY 2',
                    (prefeitura_pk, 'ATIVA'),
                )
                lojas = [{'id': r[0], 'nome': r[1]} for r in cur.fetchall()]
            finally:
                conn.close()
            cache.set(cache_key, lojas, 300)

        return JsonResponse({'lojas': lojas})
    except Exception:
        logger.exception('Falha ao buscar lojas da prefeitura %s', prefeitura_id)
        return JsonResponse({'lojas': []})


@web_login_required
def excluir_candidato(request, pk):
    """Exclui um candidato (AJAX POST) — remove o card da coluna Suplica."""
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
    from .oficialato import pode_ver_candidato
    if not pode_ver_candidato(candidato.revisao_atual, papel):
        return JsonResponse({'erro': 'Sem permissão — candidato fora da sua fase.'}, status=403)

    candidato.delete()

    # Invalida cache do kanban para atualizar KPIs
    _invalidar_cache_kanban(tenant_id)

    return JsonResponse({'ok': True})


@web_login_required
def candidato_pode_visualizar(candidato):
    """True quando o candidato já enviou a ficha (status avançado o suficiente para
    justificar um detalhe completo no sistema)."""
    return candidato.token_used_at is not None or candidato.status in (
        Candidato.Status.EM_REVISAO,
        Candidato.Status.APROVADO,
        Candidato.Status.INICIADO,
    )


@web_login_required
def candidato_detalhe(request, pk):
    """Detalhe do candidato (Súplica) — exibe dados e estado da revisão.

    Visível para todo o oficialato e admin (todos com acesso ao sistema podem
    VER); só o oficial da vez pode agir (aprovar/encaminhar/devolver).
    Só é exibido quando o candidato já enviou a ficha.
    """
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

    from .oficialato import pode_ver_candidato
    if not pode_ver_candidato(candidato.revisao_atual, papel):
        return JsonResponse({'erro': 'Sem permissão — candidato fora da sua fase.'}, status=403)

    if not candidato_pode_visualizar(candidato):
        return JsonResponse({'erro': 'Ficha ainda não enviada'}, status=404)

    return render(request, 'candidatos/detalhe.html', {
        'candidato': candidato,
    })


@web_login_required
def candidato_modal_detalhe(request, pk):
    """Retorna os dados do candidato para o modal de detalhe no kanban.

    Apenas DM e Prefeito podem ver. Candidatos sem ficha preenchida
    (EM_ANALISE, FICHA_ENVIADA, EM_PREENCHIMENTO) são visíveis com dados
    básicos — sem a ficha completa.
    """
    if request.method != 'GET':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    papel = request.session.get('usuario', {}).get('role')
    if papel not in (ROLES_OFICIAIS + (ROLE_ADMIN_SAAS,)):
        return JsonResponse({'erro': 'Sem permissão'}, status=403)

    candidato = get_object_or_404(Candidato.objects.select_related('created_by'), pk=pk)

    if candidato.tenant_id != obter_tenant_id(request) and papel != ROLE_ADMIN_SAAS:
        return JsonResponse({'erro': 'Candidato não pertence ao tenant'}, status=403)

    from .oficialato import pode_ver_candidato
    if not pode_ver_candidato(candidato.revisao_atual, papel):
        return JsonResponse({'erro': 'Sem permissão — candidato fora da sua fase.'}, status=403)

    from .models import CandidatoObservacao

    # Resolve o nome da prefeitura a partir do UUID (igual ao card do kanban)
    from recepcao.views.helpers import prefeitura_info as _prefeitura_info

    observacoes = CandidatoObservacao.objects.filter(candidato=candidato).order_by('-created_at')[:10]

    # Quem pode VER: todo o oficialato + admin. Quem pode AGIR: só o oficial
    # da vez (nível revisao_atual), o criador na fase dele e, para a aprovação
    # definitiva, Grão Prior / Grande Chanceler / Admin.
    usuario = None
    uid = request.session.get('usuario_id')
    if uid:
        from acesso.models import Usuario as _Usuario
        usuario = _Usuario.objects.filter(pk=uid).first()

    from .oficialato import (
        NIVEL_PARA_PAPEL_ACAO,
        pode_aprovar_agora,
        pode_atuar_na_vez,
        pode_devolver,
        pode_encaminhar,
    )

    nivel = candidato.revisao_atual
    pode_observar = True
    # Aprovar/encaminhar: só quem está com o candidato na vez pode agir;
    # admin_saas tem acesso transversal e também pode aprovar/encaminhar.
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


@require_POST
def candidato_aprovar(request, pk):
    """Aprovação DEFINITIVA do candidato (status → APROVADO).

    Só Grão Prior, Grande Chanceler e Admin aprovam em definitivo — os demais
    oficiais encaminham adiante (próximo nível) ou devolvem ao anterior.
    """
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    candidato = get_object_or_404(Candidato, pk=pk)
    papel = request.session.get('usuario', {}).get('role')

    if papel not in ROLES_OFICIAIS + (ROLE_ADMIN_SAAS,):
        return JsonResponse({'erro': 'Sem permissão para aprovar'}, status=403)

    usuario = obter_usuario_sessao(request)
    autor_nome = usuario.get('nome') or 'Sistema'

    from .oficialato import aprovar_final, pode_aprovar_agora
    from acesso.models import Usuario as _Usuario

    usuario_obj = _Usuario.objects.filter(pk=request.session.get('usuario_id')).first()
    if not pode_aprovar_agora(candidato, usuario_obj, papel):
        return JsonResponse({'ok': False, 'erro': 'A aprovação final só pode ser feita pelo Grão Prior, Grande Chanceler ou Admin (candidato em revisão).'}, status=403)

    ok, _status, _nivel, erro = aprovar_final(
        candidato, papel, autor_nome,
        observacao=request.POST.get('observacao', ''),
    )
    if not ok:
        return JsonResponse({'ok': False, 'erro': erro}, status=400)

    _invalidar_cache_kanban(candidato.tenant_id)
    _enviar_email_aprovacao(request, candidato)
    return JsonResponse({'ok': True, 'mensagem': 'Candidato aprovado com sucesso.'})


def _usuario_local(request):
    """Usuario local (espelho) da sessao — usado nas regras de quem criou a súplica."""
    from acesso.models import Usuario as _Usuario
    uid = request.session.get('usuario_id')
    if not uid:
        return None
    return _Usuario.objects.filter(pk=uid).first()


@require_POST
def candidato_devolver(request, pk):
    """Devolve o candidato ao nível ANTERIOR: grava a data de devolução do nível
    atual. O botão de UI de "Devolver" deve apontar aqui.
    """
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    candidato = get_object_or_404(Candidato, pk=pk)
    papel = request.session.get('usuario', {}).get('role')

    if papel not in ROLES_OFICIAIS + (ROLE_ADMIN_SAAS,):
        return JsonResponse({'erro': 'Sem permissão para devolver'}, status=403)

    usuario = obter_usuario_sessao(request)
    autor_nome = usuario.get('nome') or 'Sistema'

    from .oficialato import devolver_nivel_captura_data

    ok, _novo_nivel, erro = devolver_nivel_captura_data(
        candidato, papel, autor_nome,
        observacao=request.POST.get('observacao', ''),
    )
    if not ok:
        return JsonResponse({'ok': False, 'erro': erro}, status=400)

    _invalidar_cache_kanban(candidato.tenant_id)
    _enviar_email_devolucao(request, candidato)
    return JsonResponse({'ok': True, 'mensagem': 'Candidato devolvido ao nível anterior. E-mail enviado ao candidato.'})


@require_POST
def candidato_aprovar_ou_encaminhar(request, pk):
    """Approvação de nível: reputa o candidato e o encaminha para o próximo
    oficial, gravando a data de aprovação do nível atual.

    Só quem está com o candidato na vez pode aprovar/encaminhar; o admin_saas
    também pode. O botão de UI de "Aprovar" deve apontar aqui.
    """
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    candidato = get_object_or_404(Candidato, pk=pk)
    papel = request.session.get('usuario', {}).get('role')

    if papel not in ROLES_OFICIAIS + (ROLE_ADMIN_SAAS,):
        return JsonResponse({'erro': 'Sem permissão para aprovar'}, status=403)

    usuario = obter_usuario_sessao(request)
    autor_nome = usuario.get('nome') or 'Sistema'

    from .oficialato import avancar_nivel_captura_data

    ok, _novo_nivel, erro = avancar_nivel_captura_data(
        candidato, papel, autor_nome,
        observacao=request.POST.get('observacao', ''),
    )
    if not ok:
        return JsonResponse({'ok': False, 'erro': erro or 'Falha ao aprovar.'}, status=400)

    _invalidar_cache_kanban(candidato.tenant_id)
    _enviar_email_encaminhamento(request, candidato)
    return JsonResponse({'ok': True, 'mensagem': 'Candidato aprovado e encaminhado para a próxima revisão.'})


@require_POST
def candidato_aprovar_encaminhar(request, pk):
    """Aprovação de nível via botão "Aprovar": reputa quem está na vez no nível
    atual e encaminha para o próximo oficial. Mesma lógica do modal."""
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    candidato = get_object_or_404(Candidato, pk=pk)
    papel = request.session.get('usuario', {}).get('role')

    if papel not in ROLES_OFICIAIS + (ROLE_ADMIN_SAAS,):
        return JsonResponse({'erro': 'Sem permissão para aprovar'}, status=403)

    usuario = obter_usuario_sessao(request)
    autor_nome = usuario.get('nome') or 'Sistema'

    from .oficialato import avancar_nivel_captura_data

    ok, _novo_nivel, erro = avancar_nivel_captura_data(
        candidato, papel, autor_nome,
        observacao=request.POST.get('observacao', ''),
    )
    if not ok:
        return JsonResponse({'ok': False, 'erro': erro or 'Falha ao aprovar.'}, status=400)

    _invalidar_cache_kanban(candidato.tenant_id)
    _enviar_email_encaminhamento(request, candidato)
    return JsonResponse({'ok': True, 'mensagem': 'Aprovado e encaminhado para o próximo nível.'})


def _enviar_email_aprovacao(request, candidato):
    """Envia e-mail de aprovação ao candidato."""
    try:
        link = _gerar_link_candidato(request, candidato)
        corpo = f'''
Prezado(a) {candidato.nome_completo.split()[0] if candidato.nome_completo else 'Candidato'},

Parabéns! Sua candidatura foi aprovada pelo Grande Priorado Retificado do Brasil.

Agora você pode acessar o portal do candidato para completar seu cadastro:

{link}

Atenciosamente,
Grande Priorado Retificado do Brasil — SAL do RER
'''
        msg = EmailMultiAlternatives(
            '✓ Candidatura Aprovada — Grande Priorado Retificado do Brasil',
            corpo,
            settings.DEFAULT_FROM_EMAIL,
            [candidato.email],
        )
        msg.send(fail_silently=True)
    except Exception:
        logger.exception('Falha ao enviar e-mail de aprovação (candidato %s)', candidato.id)


def _enviar_email_encaminhamento(request, candidato):
    """Envia e-mail de encaminhamento ao candidato."""
    try:
        link = _gerar_link_candidato(request, candidato)
        corpo = f'''
Prezado(a) {candidato.nome_completo.split()[0] if candidato.nome_completo else 'Candidato'},

Sua candidatura foi encaminhada para a próxima etapa de revisão.

Para completar seu cadastro, acesse:
{link}

Atenciosamente,
Grande Priorado Retificado do Brasil — SAL do RER
'''
        msg = EmailMultiAlternatives(
            '→ Candidatura Encaminhada — Grande Priorado Retificado do Brasil',
            corpo,
            settings.DEFAULT_FROM_EMAIL,
            [candidato.email],
        )
        msg.send(fail_silently=True)
    except Exception:
        logger.exception('Falha ao enviar e-mail de encaminhamento (candidato %s)', candidato.id)


def _enviar_email_devolucao(request, candidato):
    """Envia e-mail de devolução ao candidato com observações."""
    try:
        observacoes = CandidatoObservacao.objects.filter(
            candidato=candidato,
        ).order_by('-created_at')[:1]
        ultima_obs = observacoes.first()

        corpo = f'''
Prezado(a) {candidato.nome_completo.split()[0] if candidato.nome_completo else 'Candidato'},

Sua candidatura foi devolvida para revisão.

Observações recebidas:

{ultima_obs.texto if ultima_obs else 'Sem observações adicionais.'}

Por favor, ajuste os itens acima e reenvie sua candidatura quando estiver pronto.

Atenciosamente,
Grande Priorado Retificado do Brasil — SAL do RER
'''
        msg = EmailMultiAlternatives(
            '✕ Candidatura Devolvida — Grande Priorado Retificado do Brasil',
            corpo,
            settings.DEFAULT_FROM_EMAIL,
            [candidato.email],
        )
        msg.send(fail_silently=True)
    except Exception:
        logger.exception('Falha ao enviar e-mail de devolução (candidato %s)', candidato.id)


@require_POST
def candidato_definir_senha(request, token):
    """View pública: candidato define sua senha e preenche dados complementares."""
    candidato = get_object_or_404(
        Candidato,
        access_token=token,
        token_expires_at__gt=timezone.now(),
        token_used_at__isnull=True,
    )

    senha = request.POST.get('senha', '')
    confirmar_senha = request.POST.get('confirmar_senha', '')

    if not senha or len(senha) < 8:
        return JsonResponse({'erros': ['Senha deve ter pelo menos 8 caracteres']}, status=400)

    if senha != confirmar_senha:
        return JsonResponse({'erros': ['Senhas não conferem']}, status=400)

    # Hash da senha (bcrypt via Django)
    candidato.password_hash = make_password(senha)

    # Marca token como usado
    candidato.token_used_at = timezone.now()
    candidato.status = Candidato.Status.EM_REVISAO
    # A ficha enviada NÃO pula para o Prefeito: o candidato fica com quem criou
    # a súplica (Deputado ou Prefeito) e só avança quando o criador aprovar.
    if not candidato.revisao_atual:
        from .oficialato import nivel_inicial_do_criador
        criador = candidato.created_by
        candidato.revisao_atual = nivel_inicial_do_criador(
            criador.role if criador else None,
        )
    candidato.save(update_fields=[
        'password_hash',
        'token_used_at',
        'status',
        'revisao_atual',
        'updated_at',
    ])

    return JsonResponse({
        'ok': True,
        'mensagem': 'Senha definida com sucesso! Sua ficha será analisada.',
    })


def _parse_data(valor):
    """Converte 'YYYY-MM-DD' em date; vazio/inválido devolve None."""
    from datetime import date
    if not valor:
        return None
    try:
        return date.fromisoformat(valor[:10])
    except (ValueError, TypeError):
        return None


def candidato_formulario(request, token):
    """View pública: candidato preenche a ficha completa (Súplica) e define senha."""
    candidato = get_object_or_404(
        Candidato,
        access_token=token,
        token_expires_at__gt=timezone.now(),
    )

    # Se já definiu senha (ficha enviada), mostra confirmação
    if candidato.token_used_at:
        return render(request, 'candidatos/sucesso.html', {'candidato': candidato})

    # Candidato abriu o convite mas ainda não enviou → "Em preenchimento"
    if candidato.status == Candidato.Status.FICHA_ENVIADA:
        Candidato.objects.filter(pk=candidato.pk).update(
            status=Candidato.Status.EM_PREENCHIMENTO,
        )
        candidato.status = Candidato.Status.EM_PREENCHIMENTO

    if request.method == 'POST':
        erros = []

        nome_completo = request.POST.get('nome_completo', '').strip()
        cpf = request.POST.get('cpf', '').strip()
        senha = request.POST.get('senha', '')
        confirmar_senha = request.POST.get('confirmar_senha', '')
        foto = request.FILES.get('foto')

        if not nome_completo:
            erros.append('Nome completo é obrigatório')
        if not cpf:
            erros.append('CPF é obrigatório')
        elif Candidato.objects.filter(
            tenant_id=candidato.tenant_id, cpf=cpf,
        ).exclude(pk=candidato.pk).exists():
            erros.append('Já existe um candidato com este CPF')
        if not foto:
            erros.append('A fotografia é obrigatória')
        if len(senha) < 8:
            erros.append('A senha deve ter pelo menos 8 caracteres')
        if senha != confirmar_senha:
            erros.append('As senhas não conferem')

        if erros:
            return render(request, 'candidatos/formulario.html', {
                'candidato': candidato,
                'token': token,
                'primeiro_nome': candidato.nome_completo.split()[0] if candidato.nome_completo else '',
                'erros': erros,
            })

        candidato.nome_completo = nome_completo
        candidato.cpf = cpf
        candidato.data_nascimento = _parse_data(request.POST.get('data_nascimento'))
        candidato.estado_civil = request.POST.get('estado_civil', '')
        candidato.nacionalidade = request.POST.get('nacionalidade', '') or 'Brasileira'
        candidato.natural_cidade = request.POST.get('natural_cidade', '')
        candidato.pai = request.POST.get('pai', '')
        candidato.mae = request.POST.get('mae', '')
        candidato.email = request.POST.get('email', '')
        candidato.celular = request.POST.get('celular', '')
        candidato.telefone_urgencia = request.POST.get('telefone_urgencia', '')
        candidato.identidade_numero = request.POST.get('identidade_numero', '')
        candidato.orgao_emissor = request.POST.get('orgao_emissor', '')
        candidato.data_emissao = _parse_data(request.POST.get('data_emissao'))
        candidato.endereco_logradouro = request.POST.get('endereco_logradouro', '')
        candidato.endereco_numero = request.POST.get('endereco_numero', '')
        candidato.endereco_complemento = request.POST.get('endereco_complemento', '')
        candidato.endereco_bairro = request.POST.get('endereco_bairro', '')
        candidato.endereco_cep = request.POST.get('endereco_cep', '')
        candidato.endereco_cidade = request.POST.get('endereco_cidade', '')
        candidato.endereco_uf = request.POST.get('endereco_uf', '').upper()
        candidato.loja_simbolo = request.POST.get('loja_simbolo', '')
        candidato.numero_loja_simbolo = request.POST.get('numero_loja_simbolo', '')
        candidato.data_exaltacao = _parse_data(request.POST.get('data_exaltacao'))
        candidato.potencia_simbolo = request.POST.get('potencia_simbolo', '')
        candidato.rito_loja_simbolo = request.POST.get('rito_loja_simbolo', '')

        if foto:
            candidato.foto = foto
        if request.FILES.get('quitacao'):
            candidato.quitacao_url = request.FILES.get('quitacao')
        if request.FILES.get('pagamento'):
            candidato.pagamento_url = request.FILES.get('pagamento')

        candidato.password_hash = make_password(senha)
        candidato.token_used_at = timezone.now()
        candidato.status = Candidato.Status.EM_REVISAO
        # A ficha enviada fica com o CRIADOR (Deputado ou Prefeito) — só ele
        # aprova; depois disso o candidato segue para o Prefeito da prefeitura.
        if not candidato.revisao_atual:
            from .oficialato import nivel_inicial_do_criador
            criador = candidato.created_by
            candidato.revisao_atual = nivel_inicial_do_criador(
                criador.role if criador else None,
            )
        candidato.save()

        return render(request, 'candidatos/sucesso.html', {'candidato': candidato})

    return render(request, 'candidatos/formulario.html', {
        'candidato': candidato,
        'token': token,
        'primeiro_nome': candidato.nome_completo.split()[0] if candidato.nome_completo else '',
    })
