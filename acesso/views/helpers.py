"""Funções auxiliares compartilhadas entre views de acesso."""

import logging

from django.contrib.auth.hashers import make_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import models
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.text import slugify

from acesso.ativacao import LIMITE_REENVIOS
from acesso.context_processors import ROLE_LABELS
from acesso.decorators import pode_gerir_usuarios
from acesso.models import (
    ROLE_ADMIN_SAAS,
    ROLE_VIEWER,
    ROLES_ATRIB_CRIACAO,
    SENHA_PENDENTE,
    USUARIO_PENDENTE_SENHA,
    Tenant,
    Usuario,
)
from acesso.session import iniciar_sessao
from acesso.tenant_context import resolve_tenant_id
from core.gprb import autenticar_usuario as gprb_autenticar
from core.gprb import existe_usuario as gprb_existe_usuario
from core.gprb import (
    obter_usuario_sistema,
    opcoes_lojas_usuario,
    opcoes_perfis_usuario,
    opcoes_prefeituras_usuario,
)
from recepcao.models import EtapaFunil
import psycopg
from django.core.signing import BadSignature

logger = logging.getLogger(__name__)

_HASH_DUMMY = make_password('usuario-inexistente-dummy')
_SALDORER_HOSTS = ('saldoreaa.cloud', 'www.saldoreaa.cloud')

_GPRB_ROLE_MAP = {
    'SYS_ADMIN': ROLE_ADMIN_SAAS,
    'ADMIN_LOJA': ROLE_VIEWER,
    'OPERADOR': ROLE_VIEWER,
    'GRANDE_PRIOR': 'grande_prior',
    'GRANDE_CHANCELER': 'grande_chanceler',
    'GRANDE_TESOUREIRO': 'grande_tesoureiro',
    'GRANDE_SECRETARIO': 'grande_secretario',
    'PREFEITO': 'prefeito',
    'DEPUTADO': 'deputado_mestre',
    'DEPUTADO_MESTRE': 'deputado_mestre',
    'MEMBER': ROLE_VIEWER,
}


def tenant_gprb_local():
    """Tenant local que representa a organizacao GPRB."""
    tenant = Tenant.objects.filter(slug='gprb').first()
    if tenant is None:
        tenant = Tenant.objects.create(nome='GPRB', slug='gprb')
    return tenant


def client_ip(request) -> str:
    """IP do cliente para fins de rate limiting."""
    # Fallback de IP para CHAVE de rate limit — nao e bind de socket (falso positivo).
    return request.META.get('REMOTE_ADDR', '') or '0.0.0.0'  # nosec B104


def is_saldorer(request) -> bool:
    """Detecta se a requisicao veio do Saldorer."""
    host = request.get_host().split(':')[0].lower()
    if any(host == h or host.endswith('.' + h) for h in _SALDORER_HOSTS):
        return True
    port = request.get_host().split(':')[1] if ':' in request.get_host() else ''
    return port == '3000'


def gprb_autenticar_seguro(login_id, senha):
    """Autentica no banco GPRB sem estourar excecao."""
    try:
        user = gprb_autenticar(login_id, senha)
        if user is not None:
            return user, True
        return None, gprb_existe_usuario(login_id)
    except (psycopg.Error, OSError, ValueError) as e:
        logger.error('Erro na autenticacao GPRB para %s: %s', login_id, e)
        return None, None


def entrar_com_usuario_gprb(request, gprb_user, senha, origem='gprb'):
    """Abre sessao com um usuario autenticado no banco GPRB."""
    local_user = Usuario.objects.filter(email__iexact=gprb_user['email']).first()
    crm_role = _GPRB_ROLE_MAP.get(gprb_user['role'], ROLE_VIEWER)
    tenant_gprb = None if crm_role == ROLE_ADMIN_SAAS else tenant_gprb_local()
    celular_gprb = gprb_user.get('login_identifier') or ''
    if local_user is None:
        local_user = Usuario.objects.create(
            nome=gprb_user['name'] or gprb_user['email'] or '',
            email=gprb_user['email'],
            celular=celular_gprb,
            senha=make_password(senha),
            role=crm_role,
            tenant=tenant_gprb,
        )
    else:
        if local_user.nome != (gprb_user['name'] or local_user.nome):
            local_user.nome = gprb_user['name'] or local_user.nome
        if not local_user.celular and celular_gprb:
            local_user.celular = celular_gprb
        if local_user.role != crm_role:
            local_user.role = crm_role
        if crm_role == ROLE_ADMIN_SAAS:
            local_user.tenant = None
        elif local_user.tenant_id is None:
            local_user.tenant = tenant_gprb
        if not local_user.senha or local_user.senha == SENHA_PENDENTE:
            local_user.senha = make_password(senha)
        local_user.save(update_fields=['nome', 'celular', 'role', 'senha', 'tenant', 'updated_at'])
    request.session.flush()
    iniciar_sessao(
        request, local_user,
        nicho=local_user.tenant.nicho if local_user.tenant else '',
        dispositivo=(request.META.get('HTTP_USER_AGENT', '') or '')[:140],
    )
    request.session['origem'] = origem
    return local_user


def guard_equipe(request):
    """Redireciona se o usuario nao pode gerir equipe.

    O tenant efetivo vem de resolve_tenant_id (a seleção SaaS do admin da
    plataforma fica em chave própria da sessão, não no snapshot). Sem tenant
    selecionado, o admin_saas ainda pode consultar (vê tudo); escritas são
    bloqueadas por web_requer_tenant_context nas views.
    """
    if not pode_gerir_usuarios(request):
        return redirect('dashboard:index')
    if resolve_tenant_id(request) is None:
        role = request.session.get('usuario', {}).get('role')
        if role != ROLE_ADMIN_SAAS:
            return redirect('dashboard:index')
    if Usuario.objects.filter(id=request.session.get('usuario_id')).first() is None:
        return redirect('acesso:login')
    return None


def qs_escopo(tid, qs):
    """Escopa o queryset ao tenant do gestor."""
    if tid is not None:
        return qs.filter(tenant_id=tid)
    return qs


def usuarios_locais_ativos(tid, emails_vistos, *, q='', perfil='', loja='', status=''):
    """Usuarios locais ativos do tenant ainda nao listados."""
    if status and status.upper() not in ('', 'ACTIVE'):
        return []
    if loja:
        return []
    qs = qs_escopo(tid, Usuario.objects.exclude(status=USUARIO_PENDENTE_SENHA))
    if q:
        qs = qs.filter(
            models.Q(nome__icontains=q) | models.Q(email__icontains=q) | models.Q(celular__icontains=q)
        )
    if perfil:
        qs = qs.filter(role=perfil)
    resultado = []
    for u in qs.order_by('nome', 'email'):
        email_key = u.email.lower()
        if email_key in emails_vistos:
            continue
        emails_vistos.add(email_key)
        resultado.append({
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
    return resultado


def usuarios_locais_pendentes(tid, emails_gprb, *, q='', perfil='', status=''):
    """Usuarios locais pendentes de ativacao que ainda nao existem no GPRB."""
    qs = qs_escopo(tid, Usuario.objects.filter(status=USUARIO_PENDENTE_SENHA))
    if q:
        qs = qs.filter(
            models.Q(nome__icontains=q) | models.Q(email__icontains=q) | models.Q(celular__icontains=q)
        )
    if perfil:
        qs = qs.filter(role=perfil)
    if status and status.upper() != 'PENDENTE':
        return []
    resultado = []
    for u in qs.order_by('nome', 'email'):
        if u.email.lower() in emails_gprb:
            continue
        resultado.append({
            'id': u.id,
            'gprb': False,
            'nome': u.nome,
            'email': u.email,
            'loja_nome': '',
            'loja_numero': '',
            'loja_display': '—',
            'papel': u.role,
            'papel_label': ROLE_LABELS.get(u.role, u.role),
            'ultimo_acesso': None,
            'status_code': 'PENDENTE',
            'status_label': 'Aguardando ativação',
            'pendente': True,
            'pode_reenviar': u.reenvios_ativacao < LIMITE_REENVIOS,
            'celular': u.celular,
        })
    return resultado


def opcoes_equipe_gprb():
    """Carrega opcoes de filtro do GPRB."""
    try:
        return {
            'lojas': opcoes_lojas_usuario(),
            'perfis': opcoes_perfis_usuario(),
            'gprb_ok': True,
        }
    except (psycopg.Error, OSError, ValueError) as e:
        logger.warning('GPRB indisponivel para opcoes de equipe: %s', e)
        perfis = [{'key': r, 'label': ROLE_LABELS.get(r, r)} for r in ROLES_ATRIB_CRIACAO]
        return {'lojas': [], 'perfis': perfis, 'gprb_ok': False}


def sessoes_do_usuario(usuario_id, atual_key):
    """Sessoes ativas do usuario na tabela de sessoes do Django."""
    itens = []
    agora = timezone.now()
    for s in Session.objects.filter(expire_date__gt=agora):
        try:
            dados = s.get_decoded()
        except BadSignature as e:
            logger.warning('Erro ao decodificar sessao %s: %s', s.session_key, e)
            continue
        if dados.get('usuario_id') != usuario_id:
            continue
        itens.append({
            'key': s.session_key,
            'atual': s.session_key == atual_key,
            'dispositivo': dados.get('dispositivo') or 'Sessão antiga',
            'expira': s.expire_date,
        })
    itens.sort(key=lambda x: x['atual'], reverse=True)
    return itens


def chave_etapa(tid, nome):
    """Chave interna unica por tenant a partir do nome."""
    base = slugify(nome) or 'etapa'
    existentes = set(EtapaFunil.objects.filter(tenant_id=tid).values_list('key', flat=True))
    chave, n = base, 2
    while chave in existentes or chave in ('fechado', 'perdido'):
        chave = f'{base}_{n}'
        n += 1
    return chave


def validar_email(email, erros):
    """Valida formato de e-mail."""
    email = (email or '').strip().lower()
    if not email:
        erros.append('Informe o e-mail.')
        return None
    try:
        validate_email(email)
    except DjangoValidationError:
        erros.append('Informe um e-mail válido.')
    return email


def usuario_para_edicao(user_id, tid):
    """Localiza o usuario alvo para edicao/exclusao."""
    if user_id.isdigit():
        u = qs_escopo(tid, Usuario.objects.all()).filter(pk=user_id).first()
        if u is None:
            return None, None
        return {
            'id': u.id,
            'gprb': False,
            'nome': u.nome,
            'email': u.email,
            'celular': u.celular or '',
            'papel': u.role,
            'status_code': 'PENDENTE' if u.pendente_ativacao else 'ACTIVE',
            'status_label': 'Aguardando ativação' if u.pendente_ativacao else 'Ativo',
            'prefeitura_id': u.prefeitura_id or '',
        }, u
    gprb_user = obter_usuario_sistema(user_id)
    if gprb_user is not None:
        gprb_user['gprb'] = True
        espelho = Usuario.objects.filter(email__iexact=gprb_user['email']).first()
        return gprb_user, espelho
    return None, None


def prefeituras_para_form():
    try:
        return opcoes_prefeituras_usuario()
    except (psycopg.Error, OSError, ValueError) as e:
        logger.warning('Erro ao carregar prefeituras para formulario: %s', e)
        return []
