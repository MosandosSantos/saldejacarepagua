"""Endpoints de carteiras (/api/v1/carteiras) — isoladas por tenant (escopo do token).

Sprint 3 do PRD HAZON — Gestão de bases (3.1): listar, criar e excluir carteiras;
contatos podem ser associados a uma carteira pelo `carteira_id` no payload do contato.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from api.v1.deps import get_scope, require_edicao
from api.v1.schemas.contato import CarteiraOut, CarteiraPayload
from contatos.models import Carteira

router = APIRouter()


@router.get('', response_model=list[CarteiraOut])
def listar_carteiras(
    scope: dict = Depends(get_scope),
):
    qs = Carteira.objects.all() if scope['tenant_id'] is None else Carteira.objects.filter(tenant_id=scope['tenant_id'])
    itens = []
    for c in qs.prefetch_related('contatos'):
        item = {
            'id': c.id,
            'nome': c.nome,
            'descricao': c.descricao,
            'total_contatos': c.contatos.count(),
            'created_at': c.created_at,
        }
        itens.append(item)
    return itens


@router.post('', response_model=CarteiraOut, status_code=status.HTTP_201_CREATED)
def criar_carteira(
    payload: CarteiraPayload,
    scope: dict = Depends(get_scope),
    _=Depends(require_edicao),
):
    tid = scope['tenant_id']
    nome = payload.nome.strip()
    if not nome:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='nome da carteira é obrigatório')
    qs = Carteira.objects.all() if tid is None else Carteira.objects.filter(tenant_id=tid)
    if qs.filter(nome__iexact=nome).exists():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='carteira ja existe')
    carteira = Carteira(nome=nome, descricao=payload.descricao.strip())
    if tid is not None:
        carteira.tenant_id = tid
    carteira.save()
    return {
        'id': carteira.id,
        'nome': carteira.nome,
        'descricao': carteira.descricao,
        'total_contatos': 0,
        'created_at': carteira.created_at,
    }


@router.delete('/{carteira_id}', status_code=status.HTTP_204_NO_CONTENT)
def excluir_carteira(
    carteira_id: int,
    scope: dict = Depends(get_scope),
    _=Depends(require_edicao),
):
    qs = Carteira.objects.all() if scope['tenant_id'] is None else Carteira.objects.filter(tenant_id=scope['tenant_id'])
    if not qs.filter(pk=carteira_id).delete()[0]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='carteira nao encontrada')
