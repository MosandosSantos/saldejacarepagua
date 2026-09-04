"""Views de contatos — pacote dividido por dominio (crud, negocios, notas/tags, etc.).

O __init__ reexporta todas as views para manter `from contatos import views`
funcionando nos urls.py (core e do app).
"""

from contatos.views.campos import campos_personalizados, editar_campo, excluir_campo
from contatos.views.captura import captura_lead
from contatos.views.carteiras import carteira_detalhe, carteiras
from contatos.views.crud import detalhe, editar, excluir, leads_pobres, lista, novo, membro_detalhe, membro_editar, membro_excluir, prefeituras, prefeitura_nova, prefeitura_editar, prefeitura_excluir, prefeitura_lojas_json, loja_membros_json, lojas, loja_nova, loja_detalhe, loja_editar, loja_excluir
from contatos.views.exportacao import exportar_csv, exportar_negocios_csv
from contatos.views.importacao import baixar_modelo, importar
from contatos.views.negocios import (
    negocio_editar,
    negocio_excluir,
    negocio_novo,
    negocio_tornar_principal,
    orcamento_pdf,
)
from contatos.views.notas_tags import adicionar_nota, adicionar_tag, excluir_nota, remover_tag

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
    'membro_detalhe',
    'membro_editar',
    'membro_excluir',
    'negocio_editar',
    'negocio_excluir',
    'negocio_novo',
    'negocio_tornar_principal',
    'novo',
    'orcamento_pdf',
    'prefeituras',
    'prefeitura_nova',
    'prefeitura_editar',
    'prefeitura_excluir',
    'prefeitura_lojas_json',
    'loja_membros_json',
    'lojas',
    'loja_nova',
    'loja_detalhe',
    'loja_editar',
    'loja_excluir',
    'remover_tag',
]
