"""Web endpoint for selecting an effective tenant as the SaaS administrator."""

from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from acesso.decorators import web_login_required
from acesso.models import ROLE_ADMIN_SAAS, Tenant
from acesso.tenant_context import parse_tenant_id


def _redirect_to_local_next(request):
    destination = request.POST.get('next', '')
    if (
        destination.startswith('/')
        and not destination.startswith('//')
        and url_has_allowed_host_and_scheme(
            destination,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        )
    ):
        return redirect(destination)
    return redirect('dashboard:index')


@web_login_required
@require_POST
def selecionar_tenant_contexto(request):
    """Set or clear the SaaS tenant selection stored outside identity data."""
    usuario = getattr(request, 'usuario_logado', None)
    snapshot = request.session.get('usuario', {})
    role = getattr(usuario, 'role', None) or (
        snapshot.get('role') if isinstance(snapshot, dict) else None
    )
    if role != ROLE_ADMIN_SAAS:
        return _redirect_to_local_next(request)

    raw_tenant_id = request.POST.get('tenant_id', '').strip()
    if not raw_tenant_id:
        request.session.pop('admin_tenant_id', None)
        return _redirect_to_local_next(request)

    tenant_id = parse_tenant_id(raw_tenant_id)
    if tenant_id is not None and Tenant.objects.filter(pk=tenant_id).exists():
        request.session['admin_tenant_id'] = tenant_id

    return _redirect_to_local_next(request)
