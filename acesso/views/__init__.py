"""Re-exporta todas as views para manter compatibilidade com urls.py e imports legados."""

from acesso.views.auth import alternar_tema, login_web, logout_web
from acesso.views.config import ativar_conta, config, convidar
from acesso.views.equipe import equipe, equipe_editar, equipe_excluir, equipe_novo
from acesso.views.tenant_context import selecionar_tenant_contexto

__all__ = [
    'alternar_tema',
    'ativar_conta',
    'config',
    'convidar',
    'equipe',
    'equipe_editar',
    'equipe_excluir',
    'equipe_novo',
    'login_web',
    'logout_web',
    'selecionar_tenant_contexto',
]
