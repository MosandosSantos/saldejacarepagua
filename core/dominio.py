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

NICHO_PADRAO = 'saude'
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
    'estetica': {'label': 'Estética',      'color': '#4ade80'},
    'odonto':   {'label': 'Odontologia',   'color': '#60a5fa'},
    'derma':    {'label': 'Dermatologia',  'color': '#7fe3c4'},
    'fisio':    {'label': 'Fisioterapia',  'color': '#fbbf24'},
    'nutri':    {'label': 'Nutrição',      'color': '#c084fc'},
    'psi':      {'label': 'Psicologia',    'color': '#38bdf8'},
    'geral':    {'label': 'Geral', 'color': '#fb923c'},
}

SEG_FALLBACK = {'label': '—', 'color': '#888888'}

# Opções fixas de origem do contato e forma de pagamento (compartilhadas por forms/dashboard)
ORIGENS = ['Instagram', 'Indicação', 'Google', 'WhatsApp', 'Site', 'Outro']
PAGAMENTOS = ['Particular', 'Convênio', 'Plano', 'Outro']