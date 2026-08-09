"""Rotas de usuarios — apenas admin_saas cria e lista usuarios (RBAC)."""
from fastapi import APIRouter, Depends, HTTPException, status

from api.v1.deps import require_roles
from api.v1.schemas.auth import UsuarioCreate, UsuarioOut
from api.v1.services.usuario_service import RegraViolada, UsuarioService

router = APIRouter(prefix='/usuarios', tags=['usuarios'])

_somente_admin_saas = require_roles('admin_saas')


@router.get('', response_model=list[UsuarioOut])
def listar_usuarios(
    service: UsuarioService = Depends(UsuarioService),
    _=Depends(_somente_admin_saas),
):
    return service.listar()


@router.post('', response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def criar_usuario(
    payload: UsuarioCreate,
    service: UsuarioService = Depends(UsuarioService),
    _=Depends(_somente_admin_saas),
):
    try:
        return service.criar(payload)
    except RegraViolada as erro:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(erro)
        )
