"""Acesso a dados do tema 'contatos' (Django ORM)."""
from contatos.models import Contato


class ContatoRepository:
    """Isola todas as consultas de Contato — a regra de negocio nao conhece o ORM."""

    def _base(self, tenant_id: int | None):
        """Filtro de isolamento: tenant_id None (admin_saas) enxerga tudo."""
        if tenant_id is None:
            return Contato.objects
        return Contato.objects.filter(tenant_id=tenant_id)

    def list_all(self, tenant_id: int | None = None) -> list[Contato]:
        # prefetch_related('negocios'): o ContatoOut lê stage/valor via property
        # `contato.negocio` (negocio_principal), que percorre o cache sem N+1.
        return list(self._base(tenant_id).prefetch_related('negocios').all())

    def get(self, contato_id: int, tenant_id: int | None = None) -> Contato | None:
        return (
            self._base(tenant_id)
            .prefetch_related('negocios')
            .filter(pk=contato_id)
            .first()
        )

    def create(self, dados: dict) -> Contato:
        return Contato.objects.create(**dados)

    def update(self, contato: Contato, dados: dict) -> Contato:
        for campo, valor in dados.items():
            setattr(contato, campo, valor)
        contato.save()
        contato.refresh_from_db()
        return contato

    def delete(self, contato_id: int, tenant_id: int | None = None) -> bool:
        return self._base(tenant_id).filter(pk=contato_id).delete()[0] > 0
