"""Acesso a dados de Tenant — unico ponto que toca o ORM do tema 'acesso'."""
from acesso.models import Tenant


class TenantRepository:
    def get(self, tenant_id: int):
        return Tenant.objects.filter(id=tenant_id).first()

    def get_by_slug(self, slug: str):
        return Tenant.objects.filter(slug=slug).first()

    def list_all(self):
        return list(Tenant.objects.all())

    def create(self, nome: str, slug: str):
        return Tenant.objects.create(nome=nome, slug=slug)
