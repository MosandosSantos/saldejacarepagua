"""Lead scoring — pontuação automática de contatos por origem, segmento e interação.

O score é persistido em `Contato.lead_score` e recalculado nos pontos de evento
(formulário, captura, importador, funil, notas e API). O time usa o número para
priorizar quem atender primeiro: quanto maior, mais quente o lead.
"""

# Pontos por origem do contato (quem chega por indicação tende a fechar mais)
PONTOS_ORIGEM = {
    'Indicação': 10,
    'Google': 8,
    'WhatsApp': 7,
    'Instagram': 6,
    'Site': 4,
    'Outro': 2,
}

# Pontos por segmento (nichos de maior ticket e recorrência)
PONTOS_SEGMENTO = {
    'odonto': 8,
    'derma': 6,
    'fisio': 5,
    'nutri': 5,
    'estetica': 4,
    'psi': 4,
    'geral': 3,
}

# Pontos pela etapa do negócio principal (quanto mais perto do fechamento, mais quente)
PONTOS_ETAPA = {
    'interessado': 3,
    'avaliacao_agendada': 6,
    'avaliacao_feita': 10,
    'orcamento': 15,
    'fechado': 20,
    'perdido': -8,
}

PONTOS_EMAIL = 5
PONTOS_TELEFONE = 3
PONTOS_POR_NOTA = 3
MAX_PONTOS_NOTAS = 15
PONTOS_POR_MOVIMENTACAO = 4
MAX_PONTOS_MOVIMENTACOES = 20
PONTOS_COM_VALOR = 10

LIMIAR_QUENTE = 40
LIMIAR_MORNO = 20

NIVEIS = {
    'quente': {'label': 'Quente', 'cor': '#4ade80'},
    'morno': {'label': 'Morno', 'cor': '#fbbf24'},
    'frio': {'label': 'Frio', 'cor': '#94a3b8'},
}


def nivel_do_score(total):
    """Classifica um total em quente / morno / frio (para o badge colorido)."""
    if total >= LIMIAR_QUENTE:
        return 'quente'
    if total >= LIMIAR_MORNO:
        return 'morno'
    return 'frio'


def calcular_score(contato):
    """Calcula a pontuação do contato com o detalhamento das parcelas.

    Devolve {'total': int, 'detalhes': [(rotulo, pontos), ...], 'nivel': ...,
    'nivel_label': ..., 'nivel_cor': ...} — o detalhamento alimenta o tooltip da ficha.
    """
    detalhes = []

    origem = (contato.origem or '').strip()
    if origem in PONTOS_ORIGEM:
        detalhes.append((f'Origem: {origem}', PONTOS_ORIGEM[origem]))

    seg = contato.seg or ''
    if seg in PONTOS_SEGMENTO:
        detalhes.append((f'Segmento: {seg}', PONTOS_SEGMENTO[seg]))

    if contato.email and contato.email != '—':
        detalhes.append(('E-mail informado', PONTOS_EMAIL))
    if contato.tel and contato.tel != '—' and contato.tel_normalizado:
        detalhes.append(('Telefone informado', PONTOS_TELEFONE))

    qtd_notas = contato.notas.count()
    if qtd_notas:
        detalhes.append((f'{qtd_notas} nota(s)', min(qtd_notas * PONTOS_POR_NOTA, MAX_PONTOS_NOTAS)))

    negocio = getattr(contato, 'negocio', None)
    if negocio is not None:
        if negocio.stage in PONTOS_ETAPA:
            detalhes.append((f'Etapa: {negocio.stage}', PONTOS_ETAPA[negocio.stage]))
        qtd_movs = negocio.movimentacoes.count()
        if qtd_movs:
            detalhes.append(
                (f'{qtd_movs} movimentação(ões)',
                 min(qtd_movs * PONTOS_POR_MOVIMENTACAO, MAX_PONTOS_MOVIMENTACOES))
            )
        if negocio.valor and float(negocio.valor) > 0:
            detalhes.append(('Negócio com valor', PONTOS_COM_VALOR))

    total = max(0, sum(p for _, p in detalhes))
    nivel = nivel_do_score(total)
    return {
        'total': total,
        'detalhes': detalhes,
        'nivel': nivel,
        'nivel_label': NIVEIS[nivel]['label'],
        'nivel_cor': NIVEIS[nivel]['cor'],
    }


def atualizar_score(contato, salvar=True):
    """Recomputa e persiste a pontuação de um contato (chamado nos pontos de evento).

    Evita gravar quando nada mudou (o `lead_score` fica estável entre eventos).
    """
    total = calcular_score(contato)['total']
    if contato.lead_score != total:
        contato.lead_score = total
        if salvar:
            contato.save(update_fields=['lead_score'])
    return contato.lead_score


# ---------------------------------------------------------------------------
# Completude do perfil (contato rico x pobre)
# ---------------------------------------------------------------------------
# Um lead entra "pobre" (poucos dados) e enriquece conforme a ficha é preenchida.
# A barra de perfil no kanban e o aviso na ficha usam este número para incentivar
# o time a completar os dados — perfis ricos priorizam melhor quem atender.

PESOS_COMPLETUDE = [
    ('tel', 15, 'Telefone'),
    ('email', 15, 'E-mail'),
    ('seg', 10, 'Segmento'),
    ('empresa', 10, 'Empresa'),
    ('procedimento', 10, 'Procedimento de interesse'),
    ('origem', 10, 'Origem'),
    ('cidade', 10, 'Cidade'),
    ('nascimento', 5, 'Nascimento'),
    ('observacoes', 5, 'Observações'),
    ('tags', 5, 'Tags'),
    ('valor', 5, 'Valor do negócio'),
]
PESOS_TOTAIS_COMPLETUDE = sum(p for _, p, _ in PESOS_COMPLETUDE)  # 100

LIMIAR_COMPLETUDE_RICO = 70
LIMIAR_COMPLETUDE_MEDIO = 35

NIVEIS_COMPLETUDE = {
    'rico': {'label': 'Perfil completo', 'cor': '#7fe3c4'},
    'medio': {'label': 'Perfil médio', 'cor': '#fbbf24'},
    'pobre': {'label': 'Perfil básico', 'cor': '#fb923c'},
}


def _preenchido(valor):
    """Campo considerado preenchido (vazio, espaço ou o placeholder '—' não contam)."""
    return bool(valor is not None and str(valor).strip() and str(valor).strip() != '—')


def completude_do_contato(contato, negocio=None):
    """Percentual do perfil preenchido + nível (pobre / médio / rico).

    `negocio` pode ser passado por quem já o tem em mãos (ex.: o kanban) para
    evitar a query extra do `contato.negocio` (anti N+1). Devolve
    {'total', 'nivel', 'label', 'cor', 'faltam'}.
    """
    if negocio is None:
        negocio = getattr(contato, 'negocio', None)
    valores = {
        'tel': contato.tel,
        'email': contato.email,
        'seg': contato.seg,
        'empresa': contato.empresa,
        'procedimento': contato.procedimento,
        'origem': contato.origem,
        'cidade': contato.cidade,
        'nascimento': contato.nascimento,
        'observacoes': contato.observacoes,
        'tags': bool(list(contato.tags.all())),
        'valor': bool(negocio and negocio.valor and float(negocio.valor) > 0),
    }
    pontos = 0
    faltam = []
    for campo, peso, rotulo in PESOS_COMPLETUDE:
        preenchido = bool(valores[campo]) if campo in ('tags', 'valor') else _preenchido(valores[campo])
        if preenchido:
            pontos += peso
        else:
            faltam.append(rotulo)
    total = min(PESOS_TOTAIS_COMPLETUDE, pontos)
    if total >= LIMIAR_COMPLETUDE_RICO:
        nivel = 'rico'
    elif total >= LIMIAR_COMPLETUDE_MEDIO:
        nivel = 'medio'
    else:
        nivel = 'pobre'
    info = NIVEIS_COMPLETUDE[nivel]
    return {
        'total': total,
        'nivel': nivel,
        'label': info['label'],
        'cor': info['cor'],
        'faltam': faltam,
    }
