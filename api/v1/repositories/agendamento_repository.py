"""Acesso a dados do tema 'agendamentos' (Django ORM)."""
from agendamentos.models import Agendamento


class AgendamentoRepository:
    """Isola as consultas de Agendamento com o contato relacionado."""

    def list_with_contato(self, tenant_id: int | None = None) -> list[Agendamento]:
        query = Agendamento.objects.select_related('contato')
        if tenant_id is not None:
            query = query.filter(contato__tenant_id=tenant_id)
        return list(query)
