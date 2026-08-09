"""Regras de negocio do tema 'agendamentos'."""
from datetime import date, timedelta

from api.v1.repositories.agendamento_repository import AgendamentoRepository
from api.v1.schemas.agendamento import AgendamentoOut

MESES = [
    'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
]
SEMANA = [
    'segunda-feira', 'terça-feira', 'quarta-feira',
    'quinta-feira', 'sexta-feira', 'sábado', 'domingo',
]


def dia_util(base: date, offset: int) -> date:
    """Retorna o n-esimo dia util (seg-sex) a partir de `base` — espelha o front atual."""
    dia = base
    while dia.weekday() >= 5:
        dia += timedelta(days=1)
    contados = 0
    while contados < offset:
        dia += timedelta(days=1)
        if dia.weekday() < 5:
            contados += 1
    return dia


class AgendamentoService:
    """Monta a saida de agendamentos com as datas calculadas a partir de hoje."""

    def __init__(self, repository: AgendamentoRepository):
        self._repository = repository

    def listar(self, tenant_id: int | None = None) -> list[AgendamentoOut]:
        hoje = date.today()
        return [
            self._montar(item, hoje)
            for item in self._repository.list_with_contato(tenant_id=tenant_id)
        ]

    def _montar(self, item, hoje: date) -> AgendamentoOut:
        dia = dia_util(hoje, item.offset_dias)
        return AgendamentoOut(
            hora=item.hora,
            tipo=item.tipo,
            tipoLabel=item.tipo_label,
            nome=item.contato.nome,
            empresa=item.contato.empresa,
            data=f'{dia.day:02d}/{dia.month:02d}',
            dia=f'{SEMANA[dia.weekday()]}, {dia.day} de {MESES[dia.month - 1]}',
        )
