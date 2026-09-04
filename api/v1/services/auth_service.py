"""Servico de autenticacao — login e emissao/validacao de tokens JWT (validade 7 dias)."""
from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password

from api.v1.repositories.usuario_repository import UsuarioRepository


class CredenciaisInvalidas(Exception):
    pass


def criar_hash_senha(senha: str) -> str:
    return make_password(senha)


class AuthService:
    def __init__(self, repository=None):
        self._repository = repository or UsuarioRepository()

    def autenticar(self, email: str, senha: str):
        usuario = self._repository.get_by_email(email)
        if usuario is None or not check_password(senha, usuario.senha):
            raise CredenciaisInvalidas()
        return usuario

    def gerar_token(self, usuario) -> str:
        agora = datetime.now(timezone.utc)
        payload = {
            'sub': str(usuario.id),
            'role': usuario.role,
            'tenant_id': usuario.tenant_id,
            'iss': 'gprbr',
            'iat': agora,
            'exp': agora + timedelta(days=settings.TOKEN_TTL_DIAS),
        }
        return jwt.encode(payload, settings.JWT_SECRET, algorithm='HS256')

    def decodificar_token(self, token: str) -> dict:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=['HS256'])
