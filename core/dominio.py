"""Constantes de dominio compartilhadas entre as views web (dashboard, funil, contatos).

Internamente controlam as cores das categorias; o front end (Tailwind) usa inline styles
via var(--cor) para os pontos/fases, igual ao antigo index.html.
"""

STAGES = [
    {'key': 'interessado',        'name': 'Interessado',          'color': '#94a3b8'},
    {'key': 'avaliacao_agendada', 'name': 'Avaliação agendada',   'color': '#60a5fa'},
    {'key': 'avaliacao_feita',    'name': 'Avaliação feita',      'color': '#38bdf8'},
    {'key': 'orcamento',          'name': 'Orçamento enviado',    'color': '#74b3c6'},
    {'key': 'fechado',            'name': 'Fechado',              'color': '#7fe3c4'},
    {'key': 'perdido',            'name': 'Perdido',              'color': '#ef4444'},
]

# Probabilidade de fechamento por etapa — base da receita projetada (pipeline ponderado).
PESOS_ETAPA = {
    'interessado': 0.10,
    'avaliacao_agendada': 0.25,
    'avaliacao_feita': 0.40,
    'orcamento': 0.65,
    'fechado': 1.00,
    'perdido': 0.00,
}

# As chaves dos estágios ficam fixas no banco; o nicho apenas re-rotula os nomes.
_NICHO_NOMES = {
    'ecommerce': {
        'label': 'E-commerce',
        'interessado': 'Lead capturado',
        'avaliacao_agendada': 'Contato feito',
        'avaliacao_feita': 'Qualificado',
        'orcamento': 'Proposta enviada',
        'fechado': 'Pedido fechado',
        'perdido': 'Perdido',
    },
    'saude': {
        'label': 'Saúde & estética',
        'interessado': 'Interessado',
        'avaliacao_agendada': 'Avaliação agendada',
        'avaliacao_feita': 'Avaliação feita',
        'orcamento': 'Orçamento enviado',
        'fechado': 'Fechado',
        'perdido': 'Perdido',
    },
    'odonto': {
        'label': 'Odontologia',
        'interessado': 'Interessado',
        'avaliacao_agendada': 'Consulta agendada',
        'avaliacao_feita': 'Consulta realizada',
        'orcamento': 'Orçamento enviado',
        'fechado': 'Fechado',
        'perdido': 'Perdido',
    },
    'imob': {
        'label': 'Imobiliária',
        'interessado': 'Lead novo',
        'avaliacao_agendada': 'Visita agendada',
        'avaliacao_feita': 'Visita realizada',
        'orcamento': 'Proposta enviada',
        'fechado': 'Fechado',
        'perdido': 'Perdido',
    },
    'educacao': {
        'label': 'Educação & cursos',
        'interessado': 'Interessado',
        'avaliacao_agendada': 'Aula experimental agendada',
        'avaliacao_feita': 'Aula experimental feita',
        'orcamento': 'Proposta enviada',
        'fechado': 'Matriculado',
        'perdido': 'Perdido',
    },
    'servicos': {
        'label': 'Serviços profissionais',
        'interessado': 'Interessado',
        'avaliacao_agendada': 'Reunião agendada',
        'avaliacao_feita': 'Reunião realizada',
        'orcamento': 'Proposta enviada',
        'fechado': 'Fechado',
        'perdido': 'Perdido',
    },
    'outro': {
        'label': 'Outro negócio',
        'interessado': 'Interessado',
        'avaliacao_agendada': 'Contato agendado',
        'avaliacao_feita': 'Contato feito',
        'orcamento': 'Orçamento enviado',
        'fechado': 'Fechado',
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