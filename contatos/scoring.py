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
