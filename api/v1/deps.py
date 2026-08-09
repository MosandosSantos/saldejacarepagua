"""Dependencies FastAPI — autenticacao por Bearer JWT e autorizacao por role (RBAC)."""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from acesso.models import ROLES_QUE_EDITAM
from api.v1.repositories.usuario_repository import UsuarioRepository
from api.v1.services.auth_service import AuthService

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credenciais: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    if credenciais is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='autenticacao necessaria',
            headers={'WWW-Authenticate': 'Bearer'},
        )

    try:
        payload = AuthService().decodificar_token(credenciais.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='token expirado (validade de 7 dias)',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='token invalido',
            headers={'WWW-Authenticate': 'Bearer'},
        )

    usuario = UsuarioRepository().get_by_id(int(payload['sub']))
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='usuario nao encontrado',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    return usuario


def require_roles(*roles: str):
    """Cria uma dependency que so libera o acesso para as roles listadas."""

    def depender(usuario=Depends(get_current_user)):
        if usuario.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f'sem permissao: requer uma destas roles {list(roles)}',
            )
        return usuario

    return depender


def require_edicao(usuario=Depends(get_current_user)):
    """Bloqueia o papel viewer (somente leitura) em operacoes de escrita."""
    if usuario.role not in ROLES_QUE_EDITAM:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='somente leitura: este usuario nao pode alterar dados',
        )
    return usuario


def get_scope(usuario=Depends(get_current_user)) -> dict:
    """Escopo de dados do usuario logado: tenant_id (None para admin_saas, que enxerga tudo)."""
    return {'tenant_id': usuario.tenant_id, 'role': usuario.role}
