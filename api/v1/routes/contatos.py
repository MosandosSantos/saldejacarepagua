"""Endpoints de contatos (/api/v1/contatos) — isolados por tenant (escopo do token)."""
from fastapi import APIRouter, Depends, HTTPException, status

from api.v1.deps import get_scope, require_edicao
from api.v1.repositories.contato_repository import ContatoRepository
from api.v1.schemas.contato import ContatoOut, ContatoPayload, StageUpdate
from api.v1.services.contato_service import (
    CarteiraInvalida,
    ContatoNaoEncontrado,
    ContatoService,
    StageInvalido,
)

router = APIRouter()


def get_service() -> ContatoService:
    """Fabrica com injecao de dependencia — troca facil em testes."""
    return ContatoService(ContatoRepository())


def _nao_encontrado() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='contato nao encontrado')


def _etapa_invalida() -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='etapa invalida para o tenant')


def _carteira_invalida() -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='carteira invalida para o tenant')


@router.get('', response_model=list[ContatoOut])
def listar_contatos(
    scope: dict = Depends(get_scope),
    service: ContatoService = Depends(get_service),
):
    return service.listar(tenant_id=scope['tenant_id'])


@router.post('', response_model=ContatoOut, status_code=status.HTTP_201_CREATED)
def criar_contato(
    payload: ContatoPayload,
    scope: dict = Depends(get_scope),
    _=Depends(require_edicao),
    service: ContatoService = Depends(get_service),
):
    try:
        return service.criar(payload, tenant_id=scope['tenant_id'])
    except StageInvalido:
        raise _etapa_invalida()
    except CarteiraInvalida:
        raise _carteira_invalida()


@router.get('/{contato_id}', response_model=ContatoOut)
def obter_contato(
    contato_id: int,
    scope: dict = Depends(get_scope),
    service: ContatoService = Depends(get_service),
):
    try:
        return service.obter(contato_id, tenant_id=scope['tenant_id'])
    except ContatoNaoEncontrado:
        raise _nao_encontrado()


@router.put('/{contato_id}', response_model=ContatoOut)
def atualizar_contato(
    contato_id: int,
    payload: ContatoPayload,
    scope: dict = Depends(get_scope),
    _=Depends(require_edicao),
    service: ContatoService = Depends(get_service),
):
    try:
        return service.atualizar(contato_id, payload, tenant_id=scope['tenant_id'])
    except ContatoNaoEncontrado:
        raise _nao_encontrado()
    except StageInvalido:
        raise _etapa_invalida()
    except CarteiraInvalida:
        raise _carteira_invalida()


@router.patch('/{contato_id}/stage', response_model=ContatoOut)
def mover_etapa(
    contato_id: int,
    payload: StageUpdate,
    scope: dict = Depends(get_scope),
    _=Depends(require_edicao),
    service: ContatoService = Depends(get_service),
):
    try:
        return service.mover_etapa(contato_id, payload, tenant_id=scope['tenant_id'])
    except ContatoNaoEncontrado:
        raise _nao_encontrado()
    except StageInvalido:
        raise _etapa_invalida()


@router.delete('/{contato_id}', status_code=status.HTTP_204_NO_CONTENT)
def excluir_contato(
    contato_id: int,
    scope: dict = Depends(get_scope),
    _=Depends(require_edicao),
    service: ContatoService = Depends(get_service),
):
    try:
        service.excluir(contato_id, tenant_id=scope['tenant_id'])
    except ContatoNaoEncontrado:
        raise _nao_encontrado()
