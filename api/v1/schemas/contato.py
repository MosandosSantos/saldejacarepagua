"""DTOs do tema 'contatos'."""
from datetime import date, datetime

from pydantic import BaseModel, Field


class CarteiraPayload(BaseModel):
    """Entrada de criacao/atualizacao de carteira (Sprint 3 do PRD HAZON)."""

    nome: str = Field(min_length=1, max_length=120)
    descricao: str = ''


class CarteiraOut(BaseModel):
    """Saida de uma carteira."""

    id: int
    nome: str
    descricao: str = ''
    total_contatos: int = 0
    created_at: datetime

    model_config = {'from_attributes': True}


class ContatoPayload(BaseModel):
    """Entrada de criacao/atualizacao de contato (PUT/POST)."""

    nome: str = Field(min_length=1)
    empresa: str = ''
    tel: str = ''
    email: str = ''
    seg: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    valor: float = Field(default=0, ge=0)
    procedimento: str = ''
    ultima_consulta: str = ''
    origem: str = ''
    pagamento: str = ''
    nascimento: date | None = None
    cpf: str = ''
    cidade: str = ''
    bairro: str = ''
    observacoes: str = ''
    cnpj: str = ''
    razao_social: str = ''
    cnae: str = ''
    endereco: str = ''
    responsavel: str = ''
    cargo: str = ''
    carteira_id: int | None = None


class ContatoOut(BaseModel):
    """Saida completa de um contato."""

    id: int
    nome: str
    empresa: str
    tel: str
    email: str
    seg: str
    stage: str
    valor: float
    procedimento: str
    ultima_consulta: str
    origem: str
    pagamento: str
    nascimento: date | None = None
    cpf: str = ''
    cidade: str = ''
    bairro: str = ''
    observacoes: str = ''
    cnpj: str = ''
    razao_social: str = ''
    cnae: str = ''
    endereco: str = ''
    responsavel: str = ''
    cargo: str = ''
    carteira_id: int | None = None
    updated_at: datetime

    model_config = {'from_attributes': True}


class StageUpdate(BaseModel):
    """Entrada da movimentacao de etapa (PATCH /contatos/{id}/stage)."""

    stage: str = Field(min_length=1)
