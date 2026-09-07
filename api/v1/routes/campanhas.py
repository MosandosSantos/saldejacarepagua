"""Endpoints de campanhas (/api/v1/campanhas) — isoladas por tenant (escopo do token).

Sprint 4 do PRD HAZON (4.1 — Estrutura de campanhas): listar e criar campanhas;
os envios vinculados alimentam os contadores do schema de saída.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.v1.deps import get_scope, require_edicao
from campanhas.models import Campanha

router = APIRouter()


class CampanhaIn(BaseModel):
    """Entrada de criacao de campanha."""

    nome: str = Field(min_length=1, max_length=120)
    descricao: str = ''
    canal: str = 'email'
    ativa: bool = True


class CampanhaOut(BaseModel):
    """Saida de uma campanha."""

    id: int
    nome: str
    descricao: str = ''
    canal: str
    ativa: bool
    total_envios: int = 0
    total_convertidos: int = 0


@router.get('', response_model=list[CampanhaOut])
def listar_campanhas(scope: dict = Depends(get_scope)):
    qs = Campanha.objects.all() if scope['tenant_id'] is None else Campanha.objects.filter(tenant_id=scope['tenant_id'])
    itens = []
    for c in qs.prefetch_related('envios'):
        envios = c.envios.all()
        itens.append({
            'id': c.id,
            'nome': c.nome,
            'descricao': c.descricao,
            'canal': c.canal,
            'ativa': c.ativa,
            'total_envios': envios.count(),
            'total_convertidos': envios.filter(convertido_em__isnull=False).count(),
        })
    return itens


@router.post('', response_model=CampanhaOut, status_code=status.HTTP_201_CREATED)
def criar_campanha(
    payload: CampanhaIn,
    scope: dict = Depends(get_scope),
    _=Depends(require_edicao),
):
    tid = scope['tenant_id']
    nome = payload.nome.strip()
    if not nome:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail='nome da campanha é obrigatório')
    if payload.canal not in ('email', 'whatsapp', 'telefone'):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail='canal inválido')
    qs = Campanha.objects.all() if tid is None else Campanha.objects.filter(tenant_id=tid)
    if qs.filter(nome__iexact=nome).exists():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='campanha ja existe')
    campanha = Campanha(nome=nome, descricao=payload.descricao.strip(), canal=payload.canal, ativa=payload.ativa)
    if tid is not None:
        campanha.tenant_id = tid
    campanha.save()
    return {
        'id': campanha.id,
        'nome': campanha.nome,
        'descricao': campanha.descricao,
        'canal': campanha.canal,
        'ativa': campanha.ativa,
        'total_envios': 0,
        'total_convertidos': 0,
    }
