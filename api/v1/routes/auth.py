"""Rotas de autenticacao — login (JWT) e consulta do usuario logado."""
from fastapi import APIRouter, Depends, HTTPException, status

from api.v1.deps import get_current_user
from api.v1.rate_limit import limitar
from api.v1.schemas.auth import LoginIn, TokenOut, UsuarioOut
from api.v1.services.auth_service import AuthService, CredenciaisInvalidas

router = APIRouter(prefix='/auth', tags=['auth'])


# Protecao contra forca bruta: no maximo 10 tentativas de login por minuto por IP.
@router.post('/login', response_model=TokenOut)
def login(
    payload: LoginIn,
    service: AuthService = Depends(AuthService),
    _=Depends(limitar(10, 60)),
):
    try:
        usuario = service.autenticar(payload.email, payload.senha)
    except CredenciaisInvalidas:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='email ou senha invalidos',
        )
    return TokenOut(
        access_token=service.gerar_token(usuario),
        usuario=UsuarioOut.model_validate(usuario),
    )


@router.get('/me', response_model=UsuarioOut)
def me(usuario=Depends(get_current_user)):
    return usuario
