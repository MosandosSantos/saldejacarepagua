"""Decorators da camada web (sessao, nao JWT)."""

from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from acesso.models import (
    ROLE_ADMIN_SAAS,
    ROLES_ADMINISTRATIVOS,
    ROLES_GESTORES_USUARIOS,
    ROLES_QUE_EDITAM,
)
from acesso.tenant_context import resolve_tenant_id
from core.dominio import NICHO_PADRAO

# Admins com acesso administrativo amplo: empresa + plataforma + oficialato.
ROLES_ADMIN = ROLES_ADMINISTRATIVOS

# Quem pode gerenciar usuários (criar sem senha / reenviar link) — oficialato + admin legado.
ROLES_GESTORES = ROLES_GESTORES_USUARIOS


def e_admin_do_tenant(request):
    """True quando o usuario da sessao e admin (da clinica, plataforma ou oficialato)."""
    return request.session.get('usuario', {}).get('role') in ROLES_ADMIN


def pode_editar(request):
    """True quando o usuario da sessao pode criar/editar dados (viewer nao pode).

    O oficialato edita (ROLES_QUE_EDITAM inclui os perfis RER — coexistência).
    """
    return request.session.get('usuario', {}).get('role') in ROLES_QUE_EDITAM


def pode_gerir_usuarios(request):
    """True quando o usuario da sessao pode criar usuários sem senha / reenviar links."""
    return request.session.get('usuario', {}).get('role') in ROLES_GESTORES


def web_requer_edicao(view_func):
    """Exige permissao de edicao (admin_company/operacional); viewer volta para a origem."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not pode_editar(request):
            voltar = request.META.get('HTTP_REFERER') or '/dashboard/'
            if voltar.startswith('/') and not voltar.startswith('//'):
                return redirect(voltar)
            return redirect('dashboard:index')
        return view_func(request, *args, **kwargs)
    return _wrapped


def web_requer_admin(view_func):
    """Exige admin (da clinica ou da plataforma); operacional volta para o dashboard."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not e_admin_do_tenant(request):
            return redirect('dashboard:index')
        return view_func(request, *args, **kwargs)
    return _wrapped


def web_login_required(view_func):
    """Exige sessao iniciada; redireciona para o login quando nao houver."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.session.get('usuario_id'):
            return redirect('acesso:login')
        return view_func(request, *args, **kwargs)
    return _wrapped


def web_requer_tenant_context(view_func):
    """Block unsafe SaaS writes unless a valid tenant context is selected."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.method not in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
            usuario = getattr(request, 'usuario_logado', None)
            snapshot = request.session.get('usuario', {})
            role = getattr(usuario, 'role', None) or (
                snapshot.get('role') if isinstance(snapshot, dict) else None
            )
            if role == ROLE_ADMIN_SAAS and resolve_tenant_id(request) is None:
                return HttpResponseForbidden('Selecione um tenant para alterar dados.')
        return view_func(request, *args, **kwargs)
    return _wrapped


def tenant_id_da_sessao(request):
    """Tenant efetivo do request; a seleção SaaS fica em chave própria."""
    return resolve_tenant_id(request)


def filtro_tenant(request, qs):
    """Escopa um queryset para o tenant da sessao; admin_saas (None) ve tudo."""
    tid = tenant_id_da_sessao(request)
    if tid is not None:
        return qs.filter(tenant_id=tid)
    return qs


def nicho_da_sessao(request):
    """Nicho do tenant da sessao (ramo do negocio); admin_saas usa o padrao."""
    if tenant_id_da_sessao(request) is None:
        return NICHO_PADRAO
    return request.session.get('nicho') or NICHO_PADRAO


def tenant_scope(view_func):
    """Injeta `request.scope` (dict) com o escopo do usuario logado."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        usuario = request.session.get('usuario', {})
        request.scope = {
            'tenant_id': resolve_tenant_id(request),
            'role': usuario.get('role') if isinstance(usuario, dict) else None,
        }
        return view_func(request, *args, **kwargs)
    return _wrapped
