"""Views de gerenciamento de equipe (listar, criar, editar, excluir)."""

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, models
from django.http import Http404
from django.shortcuts import redirect, render

from acesso.ativacao import (
    LIMITE_REENVIOS,
    criar_usuario_pendente,
    enviar_email_ativacao,
    reenviar_ativacao,
)
from acesso.context_processors import ROLE_LABELS
from acesso.decorators import web_login_required, web_requer_tenant_context
from acesso.models import (
    ROLES_ATRIB_CRIACAO,
    Usuario,
)
from acesso.tenant_context import resolve_tenant_id
from core.gprb import (
    ROLE_LABELS_GPRB,
    atualizar_usuario_sistema,
    excluir_usuario_sistema,
    listar_usuarios_sistema,
    opcoes_prefeituras_usuario,
)

from .helpers import (
    guard_equipe,
    opcoes_equipe_gprb,
    prefeituras_para_form,
    qs_escopo,
    usuario_para_edicao,
    usuarios_locais_ativos,
    usuarios_locais_pendentes,
)
import psycopg

logger = logging.getLogger(__name__)


@web_login_required
def _processar_reenvio_ativacao(request, tid):
    """POST 'reenviar_id' — reenvia link de ativação. Retorna (erros, sucesso, link_simulado)."""
    erros = []
    sucesso = None
    link_simulado = None
    alvo_id = request.POST.get('reenviar_id', '')
    if not alvo_id.isdigit():
        return erros, sucesso, link_simulado
    alvo = qs_escopo(tid, Usuario.objects.all()).filter(pk=alvo_id).first()
    if alvo is None:
        erros.append('Usuário não encontrado.')
    elif not alvo.pendente_ativacao:
        erros.append('Este usuário já ativou a conta — não há link para reenviar.')
    elif alvo.reenvios_ativacao >= LIMITE_REENVIOS:
        erros.append(f'Limite de {LIMITE_REENVIOS} reenvios atingido para {alvo.email}.')
    else:
        reenviar_ativacao(alvo)
        status, link = enviar_email_ativacao(request, alvo)
        sucesso = f'Novo link de ativação enviado para {alvo.email}.'
        if status == 'simulado':
            link_simulado = link
    return erros, sucesso, link_simulado


def _carregar_usuarios_equipe(tid, q, loja, perfil, status):
    """Junta usuários GPRB + locais (ativos e pendentes) conforme filtros.

    Com banco GPRB indisponível, cai no modo degradado (só locais).
    Retorna (opcoes, usuarios).
    """
    opcoes = opcoes_equipe_gprb()
    usuarios = []
    try:
        gprb_status = status if status and status.upper() != 'PENDENTE' else ''
        if not status or status.upper() != 'PENDENTE':
            usuarios = listar_usuarios_sistema(
                q=q, loja_id=loja, perfil=perfil, status=gprb_status,
            )
        emails_gprb = {u['email'].lower() for u in usuarios if u.get('email')}
        if status.upper() == 'PENDENTE':
            usuarios = usuarios_locais_pendentes(
                tid, set(), q=q, perfil=perfil, status=status,
            )
        else:
            usuarios.extend(usuarios_locais_pendentes(
                tid, emails_gprb, q=q, perfil=perfil, status=status,
            ))
            emails_vistos = {u['email'].lower() for u in usuarios if u.get('email')}
            usuarios.extend(usuarios_locais_ativos(
                tid, emails_vistos, q=q, perfil=perfil, loja=loja, status=status,
            ))
    except (psycopg.Error, OSError, ValueError):
        logger.exception('Erro ao carregar usuarios do GPRB')
        opcoes['gprb_ok'] = False
        emails_gprb = set()
        usuarios = usuarios_locais_pendentes(tid, emails_gprb, q=q, perfil=perfil, status=status)
        if not status or status.upper() == 'ACTIVE':
            qs = qs_escopo(tid, Usuario.objects.exclude(status='PENDENTE_SENHA'))
            if q:
                qs = qs.filter(
                    models.Q(nome__icontains=q) | models.Q(email__icontains=q) | models.Q(celular__icontains=q)
                )
            if perfil:
                qs = qs.filter(role=perfil)
            for u in qs.order_by('nome', 'email'):
                usuarios.append({
                    'id': u.id,
                    'gprb': False,
                    'nome': u.nome,
                    'email': u.email,
                    'loja_nome': '',
                    'loja_numero': '',
                    'loja_display': '—',
                    'papel': u.role,
                    'papel_label': ROLE_LABELS.get(u.role, u.role),
                    'ultimo_acesso': u.updated_at,
                    'status_code': 'ACTIVE',
                    'status_label': 'Ativo',
                    'pendente': False,
                    'pode_reenviar': False,
                    'celular': u.celular,
                })
    return opcoes, usuarios


@web_login_required
@web_requer_tenant_context
def equipe(request):
    """Lista de usuarios do sistema com busca e filtros."""
    if redir := guard_equipe(request):
        return redir
    tid = resolve_tenant_id(request)

    if request.method == 'POST':
        erros, sucesso, link_simulado = _processar_reenvio_ativacao(request, tid)
    else:
        erros = []
        sucesso = None
        link_simulado = None

    q = request.GET.get('q', '').strip()
    loja = request.GET.get('loja', '').strip()
    perfil = request.GET.get('perfil', '').strip()
    status = request.GET.get('status', '').strip()
    filtros_ativos = bool(q or loja or perfil or status)

    opcoes, usuarios = _carregar_usuarios_equipe(tid, q, loja, perfil, status)

    if not opcoes['perfis']:
        opcoes['perfis'] = [
            {'key': r, 'label': ROLE_LABELS.get(r, r)} for r in ROLES_ATRIB_CRIACAO
        ]

    return render(request, 'acesso/equipe.html', {
        'usuarios': usuarios,
        'erros': erros,
        'sucesso': sucesso,
        'link_simulado': link_simulado,
        'q': q,
        'loja': loja,
        'perfil': perfil,
        'status': status,
        'filtros_ativos': filtros_ativos,
        'opcoes_lojas': opcoes['lojas'],
        'opcoes_perfis': opcoes['perfis'],
        'limite_reenvios': LIMITE_REENVIOS,
    })


@web_login_required
@web_requer_tenant_context
def equipe_novo(request):
    """Formulario para criar usuario do sistema (sem senha — link de ativacao 72h)."""
    if redir := guard_equipe(request):
        return redir
    tid = resolve_tenant_id(request)
    criador = Usuario.objects.filter(id=request.session.get('usuario_id')).first()

    erros = []
    sucesso = None
    link_simulado = None
    prefeituras = []
    try:
        prefeituras = opcoes_prefeituras_usuario()
    except (psycopg.Error, OSError, ValueError) as e:
        logger.warning('Erro ao carregar prefeituras: %s', e)

    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        email = request.POST.get('email', '').strip().lower()
        celular = request.POST.get('celular', '').strip()
        papel = request.POST.get('papel', '')
        prefeitura_id = request.POST.get('prefeitura', '').strip()
        if not nome:
            erros.append('Informe o nome do usuário.')
        if not email:
            erros.append('Informe o e-mail do usuário.')
        else:
            try:
                validate_email(email)
            except DjangoValidationError:
                erros.append('Informe um e-mail válido.')
            if Usuario.objects.filter(email__iexact=email).exists():
                erros.append(f'Já existe um usuário com o e-mail {email}.')
        if not celular:
            erros.append('Informe o celular do usuário.')
        if papel not in ROLES_ATRIB_CRIACAO:
            erros.append('Escolha um perfil válido.')
        if not erros:
            try:
                novo = criar_usuario_pendente(
                    nome=nome, email=email, celular=celular, papel=papel,
                    criado_por=criador, tenant_id=tid, prefeitura_id=prefeitura_id,
                )
            except IntegrityError:
                erros.append(f'Já existe um usuário com o e-mail {email}.')
            else:
                status_envio, link = enviar_email_ativacao(request, novo)
                sucesso = (
                    f'{nome} foi cadastrado(a). Enviamos um link de ativação para '
                    f'{email} — válido por 72 horas.'
                )
                if status_envio == 'simulado':
                    link_simulado = link

    return render(request, 'acesso/equipe_novo.html', {
        'erros': erros,
        'sucesso': sucesso,
        'link_simulado': link_simulado,
        'prefeituras': prefeituras,
        'perfis': [
            {'key': r, 'label': ROLE_LABELS.get(r, r)} for r in ROLES_ATRIB_CRIACAO
        ],
        'limite_reenvios': LIMITE_REENVIOS,
    })


@web_login_required
@web_requer_tenant_context
def equipe_editar(request, user_id):
    """Edicao de um usuario do sistema (GPRB ou local)."""
    if redir := guard_equipe(request):
        return redir
    tid = resolve_tenant_id(request)

    usuario, espelho_local = usuario_para_edicao(user_id, tid)
    if usuario is None:
        raise Http404('Usuário não encontrado')

    perfis = (
        [{'key': r, 'label': ROLE_LABELS_GPRB.get(r, r)} for r in ROLE_LABELS_GPRB]
        if usuario['gprb'] else
        [{'key': r, 'label': ROLE_LABELS.get(r, r)} for r in ROLES_ATRIB_CRIACAO]
    )
    prefeituras = prefeituras_para_form()
    erros = []

    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        email = request.POST.get('email', '').strip().lower()
        celular = request.POST.get('celular', '').strip()
        papel = request.POST.get('papel', '')
        prefeitura_id = request.POST.get('prefeitura', '').strip()

        if not nome:
            erros.append('Informe o nome do usuário.')
        if not email:
            erros.append('Informe o e-mail do usuário.')
        else:
            try:
                validate_email(email)
            except DjangoValidationError:
                erros.append('Informe um e-mail válido.')
        chaves_validas = {p['key'] for p in perfis}
        if papel not in chaves_validas:
            erros.append('Escolha um perfil válido.')

        if not erros:
            if usuario['gprb']:
                atualizar_usuario_sistema(
                    user_id, nome=nome, email=email, celular=celular,
                    role=papel, prefeitura_id=prefeitura_id,
                )
                if espelho_local is not None and espelho_local.email.lower() == email:
                    espelho_local.nome = nome
                    espelho_local.save(update_fields=['nome', 'updated_at'])
            else:
                duplicado = Usuario.objects.filter(email__iexact=email).exclude(pk=usuario['id']).exists()
                if duplicado:
                    erros.append(f'Já existe um usuário com o e-mail {email}.')
                else:
                    espelho_local.nome = nome
                    espelho_local.email = email
                    espelho_local.celular = celular
                    espelho_local.role = papel
                    espelho_local.prefeitura_id = prefeitura_id
                    espelho_local.save()
        if not erros:
            return redirect('equipe')
        usuario.update({'nome': nome, 'email': email, 'celular': celular,
                        'papel': papel, 'prefeitura_id': prefeitura_id})

    return render(request, 'acesso/equipe_editar.html', {
        'u': usuario,
        'perfis': perfis,
        'prefeituras': prefeituras,
        'erros': erros,
    })


@web_login_required
@web_requer_tenant_context
def equipe_excluir(request, user_id):
    """Exclusao de um usuario do sistema."""
    if redir := guard_equipe(request):
        return redir
    tid = resolve_tenant_id(request)

    usuario, espelho_local = usuario_para_edicao(user_id, tid)
    if usuario is None:
        raise Http404('Usuário não encontrado')

    proprio = str(request.session.get('usuario_id')) == str(usuario['id']) and not usuario['gprb']
    erro = None
    if request.method == 'POST':
        if proprio:
            erro = 'Você não pode excluir o seu próprio usuário.'
        else:
            if usuario['gprb']:
                excluir_usuario_sistema(user_id)
                if espelho_local is not None and espelho_local.email.lower() == usuario['email'].lower():
                    espelho_local.delete()
            else:
                espelho_local.delete()
            return redirect('equipe')

    return render(request, 'acesso/equipe_excluir.html', {
        'u': usuario,
        'erro': erro,
        'proprio': proprio,
    })
