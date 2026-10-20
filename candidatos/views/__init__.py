"""Re-exporta todas as views para manter compatibilidade com urls.py e imports legados."""

from candidatos.views.api import api_lojas_por_prefeitura, api_prefeituras
from candidatos.views.crud import (
    candidato_detalhe,
    candidato_modal_detalhe,
    criar_candidato,
    excluir_candidato,
)
from candidatos.views.portal import (
    candidato_definir_senha,
    candidato_formulario,
    candidato_suplica,
    candidato_dashboard,
)
from candidatos.views.workflow import (
    candidato_aprovar,
    candidato_aprovar_encaminhar,
    candidato_devolver,
)

__all__ = [
    'api_lojas_por_prefeitura',
    'api_prefeituras',
    'candidato_aprovar',
    'candidato_aprovar_encaminhar',
    'candidato_detalhe',
    'candidato_definir_senha',
    'candidato_devolver',
    'candidato_formulario',
    'candidato_modal_detalhe',
    'candidato_suplica',
    'candidato_dashboard',
    'criar_candidato',
    'excluir_candidato',
]
