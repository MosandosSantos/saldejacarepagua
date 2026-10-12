"""Resolve the effective tenant without changing the authenticated identity."""

from acesso.models import ROLE_ADMIN_SAAS, Tenant

ADMIN_TENANT_SESSION_KEY = 'admin_tenant_id'
MAX_TENANT_ID = 2_147_483_647


def parse_tenant_id(value):
    """Parse a positive Tenant AutoField ID without unbounded int conversion."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 0 < value <= MAX_TENANT_ID else None
    if not isinstance(value, str) or not value.isdecimal() or len(value) > 10:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if 0 < parsed <= MAX_TENANT_ID else None


def resolve_tenant_id(request) -> int | None:
    """Return the persisted user's tenant or a validated SaaS selection.

    The SaaS selection is deliberately isolated in its own session key. It is
    never written into the user's tenant relation or identity snapshot.
    """
    session = request.session
    snapshot = session.get('usuario', {})
    if not isinstance(snapshot, dict):
        snapshot = {}

    usuario = getattr(request, 'usuario_logado', None)
    role = getattr(usuario, 'role', None) or snapshot.get('role')
    if role != ROLE_ADMIN_SAAS:
        if usuario is not None:
            return usuario.tenant_id
        return snapshot.get('tenant_id')

    selected_tenant_id = parse_tenant_id(session.get(ADMIN_TENANT_SESSION_KEY))
    if selected_tenant_id is None:
        session.pop(ADMIN_TENANT_SESSION_KEY, None)
        return None

    if Tenant.objects.filter(pk=selected_tenant_id).exists():
        return selected_tenant_id

    session.pop(ADMIN_TENANT_SESSION_KEY, None)
    return None
