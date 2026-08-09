"""Regras de negocio de usuarios e tenants (RBAC).

Papéis: admin_saas (plataforma, nao tem tenant) | admin_company e operacional (pertencem a um tenant).
Regras:
- admin_company e operacional exigem tenant_id;
- admin_saas nao pode ter tenant_id;
- email de usuario e unico.
"""
from acesso.models import ROLE_ADMIN_SAAS, ROLES_DE_TENANT
from api.v1.repositories.tenant_repository import TenantRepository
from api.v1.repositories.usuario_repository import UsuarioRepository
from api.v1.services.auth_service import criar_hash_senha


class RegraViolada(Exception):
    pass


class UsuarioService:
    def __init__(self, repository=None, tenant_repository=None):
        self._repository = repository or UsuarioRepository()
        self._tenants = tenant_repository or TenantRepository()

    def listar(self):
        return self._repository.list_all()

    def criar(self, payload) -> object:
        if payload.role in ROLES_DE_TENANT and payload.tenant_id is None:
            raise RegraViolada('os papéis de tenant (admin_company, operacional, viewer) exigem tenant_id')

        if payload.role == ROLE_ADMIN_SAAS and payload.tenant_id is not None:
            raise RegraViolada('admin_saas nao possui tenant')

        if payload.role in ROLES_DE_TENANT:
            tenant = self._tenants.get(payload.tenant_id)
            if tenant is None:
                raise RegraViolada('tenant informado nao existe')
        else:
            tenant = None

        if self._repository.get_by_email(payload.email) is not None:
            raise RegraViolada('email ja cadastrado')

        return self._repository.create(
            nome=payload.nome,
            email=payload.email,
            senha_hash=criar_hash_senha(payload.senha),
            role=payload.role,
            tenant=tenant,
        )


class TenantService:
    def __init__(self, repository=None):
        self._repository = repository or TenantRepository()

    def listar(self):
        return self._repository.list_all()

    def criar(self, payload):
        if self._repository.get_by_slug(payload.slug) is not None:
            raise RegraViolada('slug de tenant ja existe')
        return self._repository.create(nome=payload.nome, slug=payload.slug)
