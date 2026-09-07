"""Constantes de dominio compartilhadas entre as views web (dashboard, funil, contatos).

Internamente controlam as cores das categorias; o front end (Tailwind) usa inline styles
via var(--cor) para os pontos/fases, igual ao antigo index.html.
"""

STAGES = [
    {'key': 'suplica',        'name': 'Suplica',        'color': '#94a3b8'},
    {'key': 'prefeito',       'name': 'Prefeituras',    'color': '#38bdf8'},
    {'key': 'tesoureiro',     'name': 'Grande Tesoureiro',     'color': '#74b3c6'},
    {'key': 'chanceler_i',    'name': 'Grande Chanceler',    'color': '#a78bfa'},
    {'key': 'grao_prior',     'name': 'Grão Prior',     'color': '#f472b6'},
    {'key': 'chanceler_ii',   'name': 'Chanceler II',   'color': '#fb923c'},
    {'key': 'prefeito_ii',    'name': 'Prefeito II',    'color': '#4ade80'},
    {'key': 'deputado_ii',    'name': 'Deputado II',    'color': '#fbbf24'},
    {'key': 'perdido',        'name': 'Perdido',        'color': '#ef4444'},
]

# Probabilidade de fechamento por etapa — base da receita projetada (pipeline ponderado).
PESOS_ETAPA = {
    'suplica':      0.05,
    'prefeito':     0.20,
    'tesoureiro':   0.35,
    'chanceler_i':  0.50,
    'grao_prior':   0.65,
    'chanceler_ii': 0.80,
    'prefeito_ii':  0.90,
    'deputado_ii':  0.95,
    'perdido':      0.00,
}

# As chaves dos estágios ficam fixas no banco; o nicho apenas re-rotula os nomes.
_NICHO_NOMES = {
    'ecommerce': {
        'label': 'E-commerce',
        'suplica': 'Suplica',
        'prefeito': 'Prefeituras',
        'tesoureiro': 'Grande Tesoureiro',
        'chanceler_i': 'Grande Chanceler',
        'grao_prior': 'Grão Prior',
        'chanceler_ii': 'Chanceler II',
        'prefeito_ii': 'Prefeito II',
        'deputado_ii': 'Deputado II',
        'perdido': 'Perdido',
    },
    'saude': {
        'label': 'Saúde & estética',
        'suplica': 'Suplica',
        'prefeito': 'Prefeituras',
        'tesoureiro': 'Grande Tesoureiro',
        'chanceler_i': 'Grande Chanceler',
        'grao_prior': 'Grão Prior',
        'chanceler_ii': 'Chanceler II',
        'prefeito_ii': 'Prefeito II',
        'deputado_ii': 'Deputado II',
        'perdido': 'Perdido',
    },
    'odonto': {
        'label': 'Odontologia',
        'suplica': 'Suplica',
        'prefeito': 'Prefeituras',
        'tesoureiro': 'Grande Tesoureiro',
        'chanceler_i': 'Grande Chanceler',
        'grao_prior': 'Grão Prior',
        'chanceler_ii': 'Chanceler II',
        'prefeito_ii': 'Prefeito II',
        'deputado_ii': 'Deputado II',
        'perdido': 'Perdido',
    },
    'imob': {
        'label': 'Imobiliária',
        'suplica': 'Suplica',
        'prefeito': 'Prefeituras',
        'tesoureiro': 'Grande Tesoureiro',
        'chanceler_i': 'Grande Chanceler',
        'grao_prior': 'Grão Prior',
        'chanceler_ii': 'Chanceler II',
        'prefeito_ii': 'Prefeito II',
        'deputado_ii': 'Deputado II',
        'perdido': 'Perdido',
    },
    'educacao': {
        'label': 'Educação & cursos',
        'suplica': 'Suplica',
        'prefeito': 'Prefeituras',
        'tesoureiro': 'Grande Tesoureiro',
        'chanceler_i': 'Grande Chanceler',
        'grao_prior': 'Grão Prior',
        'chanceler_ii': 'Chanceler II',
        'prefeito_ii': 'Prefeito II',
        'deputado_ii': 'Deputado II',
        'perdido': 'Perdido',
    },
    'servicos': {
        'label': 'Serviços profissionais',
        'suplica': 'Suplica',
        'prefeito': 'Prefeituras',
        'tesoureiro': 'Grande Tesoureiro',
        'chanceler_i': 'Grande Chanceler',
        'grao_prior': 'Grão Prior',
        'chanceler_ii': 'Chanceler II',
        'prefeito_ii': 'Prefeito II',
        'deputado_ii': 'Deputado II',
        'perdido': 'Perdido',
    },
    'outro': {
        'label': 'Outro negócio',
        'suplica': 'Suplica',
        'prefeito': 'Prefeituras',
        'tesoureiro': 'Grande Tesoureiro',
        'chanceler_i': 'Grande Chanceler',
        'grao_prior': 'Grão Prior',
        'chanceler_ii': 'Chanceler II',
        'prefeito_ii': 'Prefeito II',
        'deputado_ii': 'Deputado II',
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
