"""Rotas de tenants — apenas admin_saas cria e lista tenants (RBAC)."""
from fastapi import APIRouter, Depends, HTTPException, status

from api.v1.deps import require_roles
from api.v1.schemas.auth import TenantIn, TenantOut
from api.v1.services.usuario_service import RegraViolada, TenantService

router = APIRouter(prefix='/tenants', tags=['tenants'])

_somente_admin_saas = require_roles('admin_saas')


@router.get('', response_model=list[TenantOut])
def listar_tenants(
    service: TenantService = Depends(TenantService),
    _=Depends(_somente_admin_saas),
):
    return service.listar()


@router.post('', response_model=TenantOut, status_code=status.HTTP_201_CREATED)
def criar_tenant(
    payload: TenantIn,
    service: TenantService = Depends(TenantService),
    _=Depends(_somente_admin_saas),
):
    try:
        return service.criar(payload)
    except RegraViolada as erro:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(erro)
        )
