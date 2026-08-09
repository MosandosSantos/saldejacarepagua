"""DTOs do tema 'agendamentos'."""
from pydantic import BaseModel


class AgendamentoOut(BaseModel):
    """Saida de um agendamento com data calculada a partir de hoje."""

    hora: str
    tipo: str
    tipoLabel: str
    nome: str
    empresa: str
    data: str
    dia: str
