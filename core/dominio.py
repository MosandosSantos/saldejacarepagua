"""Constantes de dominio compartilhadas entre as views web (dashboard, funil, contatos).

Internamente controlam as cores das categorias; o front end (Tailwind) usa inline styles
via var(--cor) para os pontos/fases, igual ao antigo index.html.
"""

STAGES = [
    {'key': 'suplica',        'name': 'Grau 4',         'color': '#94a3b8'},
    {'key': 'pagamento',      'name': 'Grau 9',         'color': '#38bdf8'},
    {'key': 'iniciacao',      'name': 'Grau 14',        'color': '#a78bfa'},
    {'key': 'grau15',         'name': 'Grau 15',        'color': '#c084fc'},
    {'key': 'comunicacao',    'name': 'Grau 18',        'color': '#4ade80'},
    {'key': 'grau19',         'name': 'Grau 19',        'color': '#f472b6'},
    {'key': 'diploma',        'name': 'Grau 22',        'color': '#fbbf24'},
    {'key': 'grau28',         'name': 'Grau 28',        'color': '#fb923c'},
    {'key': 'grau30',         'name': 'Grau 30',        'color': '#facc15'},
    {'key': 'grau31',         'name': 'Grau 31',        'color': '#fda4af'},
    {'key': 'grau32',         'name': 'Grau 32',        'color': '#e879f9'},
    {'key': 'perdido',        'name': 'Perdido',        'color': '#ef4444'},
]

# Probabilidade de fechamento por etapa — base da receita projetada (pipeline ponderado).
PESOS_ETAPA = {
    'suplica':      0.15,
    'pagamento':    0.35,
    'iniciacao':    0.60,
    'grau15':       0.70,
    'comunicacao':  0.80,
    'grau19':       0.85,
    'diploma':      0.90,
    'grau28':       0.95,
    'grau30':       0.98,
    'grau31':       0.99,
    'grau32':       1.00,
    'perdido':      0.00,
}

# As chaves dos estágios ficam fixas no banco; o nicho apenas re-rotula os nomes.
_NICHO_NOMES = {
    'ecommerce': {
        'label': 'E-commerce',
        'suplica': 'Grau 4',
        'pagamento': 'Grau 9',
        'iniciacao': 'Grau 14',
        'comunicacao': 'Grau 18',
        'perdido': 'Perdido',
    },
    'saude': {
        'label': 'Saúde & estética',
        'suplica': 'Grau 4',
        'pagamento': 'Grau 9',
        'iniciacao': 'Grau 14',
        'comunicacao': 'Grau 18',
        'perdido': 'Perdido',
    },
    'odonto': {
        'label': 'Odontologia',
        'suplica': 'Grau 4',
        'pagamento': 'Grau 9',
        'iniciacao': 'Grau 14',
        'comunicacao': 'Grau 18',
        'perdido': 'Perdido',
    },
    'imob': {
        'label': 'Imobiliária',
        'suplica': 'Grau 4',
        'pagamento': 'Grau 9',
        'iniciacao': 'Grau 14',
        'comunicacao': 'Grau 18',
        'perdido': 'Perdido',
    },
    'educacao': {
        'label': 'Educação & cursos',
        'suplica': 'Grau 4',
        'pagamento': 'Grau 9',
        'iniciacao': 'Grau 14',
        'comunicacao': 'Grau 18',
        'perdido': 'Perdido',
    },
    'servicos': {
        'label': 'Serviços profissionais',
        'suplica': 'Grau 4',
        'pagamento': 'Grau 9',
        'iniciacao': 'Grau 14',
        'comunicacao': 'Grau 18',
        'perdido': 'Perdido',
    },
    'outro': {
        'label': 'Outro negócio',
        'suplica': 'Grau 4',
        'pagamento': 'Grau 9',
        'iniciacao': 'Grau 14',
        'comunicacao': 'Grau 18',
        'perdido': 'Perdido',
    },
}

NICHO_PADRAO = 'ecommerce'
NICHOS = {k: {'label': v['label']} for k, v in _NICHO_NOMES.items()}


def stages_do_nicho(nicho):
    """STAGES com os nomes do nicho (chaves e cores permanecem as mesmas)."""
    nomes = _NICHO_NOMES.get(nicho, _NICHO_NOMES[NICHO_PADRAO])
    return [
        {'key': s['key'], 'name': nomes.get(s['key'], s['name']), 'color': s['color']}
        for s in STAGES
    ]


def stage_map_do_nicho(nicho):
    return {s['key']: s for s in stages_do_nicho(nicho)}


STAGE_MAP = {s['key']: s for s in STAGES}

SEGS = {
    'eletronicos': {'label': 'Eletrônicos',  'color': '#60a5fa'},
    'moda':        {'label': 'Moda & vestuário', 'color': '#c084fc'},
    'casa':        {'label': 'Casa & decoração', 'color': '#4ade80'},
    'beleza':      {'label': 'Beleza & cuidados', 'color': '#f472b6'},
    'esportes':    {'label': 'Esportes & lazer', 'color': '#fbbf24'},
    'alimentos':   {'label': 'Alimentos',    'color': '#fb923c'},
    'geral':       {'label': 'Geral',        'color': '#94a3b8'},
}

SEG_FALLBACK = {'label': '—', 'color': '#888888'}

# Opções fixas de origem do contato e forma de pagamento (compartilhadas por forms/dashboard)
ORIGENS = ['Instagram', 'Google Ads', 'Facebook', 'Indicação', 'WhatsApp', 'Orgânico', 'Marketplace', 'Outro']
PAGAMENTOS = ['Cartão de crédito', 'Boleto', 'Pix', 'Transferência', 'Parcelado', 'Outro']
