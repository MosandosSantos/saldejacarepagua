"""Views de contatos — pacote dividido por dominio (crud, negocios, notas/tags, etc.).

O __init__ reexporta todas as views para manter `from contatos import views`
funcionando nos urls.py (core e do app).
"""

from contatos.views.campos import campos_personalizados, editar_campo, excluir_campo
from contatos.views.captura import captura_lead
from contatos.views.carteiras import carteira_detalhe, carteiras
from contatos.views.crud import detalhe, editar, excluir, leads_pobres, lista, novo
from contatos.views.exportacao import exportar_csv, exportar_negocios_csv
from contatos.views.gprb_lojas import (
    loja_detalhe,
    loja_editar,
    loja_excluir,
    loja_membros_json,
    loja_nova,
    lojas,
)
from contatos.views.gprb_membros import membro_detalhe, membro_editar, membro_excluir
from contatos.views.gprb_prefeituras import prefeitura_lojas_json
from contatos.views.vales import (
    prefeitura_editar,
    prefeitura_excluir,
    prefeitura_nova,
    prefeituras,
)
from contatos.views.importacao import baixar_modelo, importar
from contatos.views.negocios import (
    negocio_editar,
    negocio_excluir,
    negocio_novo,
    negocio_tornar_principal,
    orcamento_pdf,
)
from contatos.views.notas_tags import (
    adicionar_nota,
    adicionar_tag,
    excluir_nota,
    remover_tag,
)

__all__ = [
    'adicionar_nota',
    'adicionar_tag',
    'baixar_modelo',
    'campos_personalizados',
    'captura_lead',
    'carteira_detalhe',
    'carteiras',
    'detalhe',
    'editar',
    'editar_campo',
    'excluir',
    'excluir_campo',
    'excluir_nota',
    'exportar_csv',
    'exportar_negocios_csv',
    'importar',
    'leads_pobres',
    'lista',
    'loja_detalhe',
    'loja_editar',
    'loja_excluir',
    'loja_membros_json',
    'loja_nova',
    'lojas',
    'membro_detalhe',
    'membro_editar',
    'membro_excluir',
    'negocio_editar',
    'negocio_excluir',
    'negocio_novo',
    'negocio_tornar_principal',
    'novo',
    'orcamento_pdf',
    'prefeitura_editar',
    'prefeitura_excluir',
    'prefeitura_lojas_json',
    'prefeitura_nova',
    'prefeituras',
    'remover_tag',
]
