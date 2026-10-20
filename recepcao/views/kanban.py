"""View principal do kanban — renderizacao, mover e excluir negocios.

Otimizado para performance:
  - Imports no topo do modulo
  - Busca OR com Q objects
  - Passa qtd_cand para evitar query duplicada
"""

import logging

from django.db.models import Max, Q
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from acesso.decorators import (
    filtro_tenant,
    nicho_da_sessao,
    pode_editar,
    tenant_id_da_sessao,
    web_login_required,
    web_requer_tenant_context,
)
from contatos.models import GrauMembro, Loja, Membro, Negocio, Vale, registrar_movimentacao
from contatos.scoring import atualizar_score
from core.dominio import ORIGENS
from recepcao.models import etapa_map_do_tenant, etapas_e_map_do_tenant
from recepcao.relatorio_iniciacao import (
    gerar_pdf_iniciacao,
    gerar_xlsx_iniciacao,
)
from recepcao.views.board import dados_board
from recepcao.views.helpers import (
    cards_candidatos,
    cards_do_kanban,
    estagnados_da_lista,
    tenant_id_da_sessao_ou_padrao,
)

logger = logging.getLogger(__name__)

# Etapas que representam graus no Flow de Iniciação (key → nº do grau).
GRAU_DA_ETAPA = {
    'suplica': 4, 'pagamento': 9, 'iniciacao': 14, 'grau15': 15,
    'comunicacao': 18, 'grau19': 19, 'diploma': 22, 'grau28': 28,
    'grau30': 30, 'grau31': 31, 'grau32': 32,
}

# Coluna de grau → grau anterior exigido da listagem: a coluna traz todos os
# membros detentores do grau anterior ao alvo (ex.: 'Grau 9' lista
# todos do grau 8; a ex-'Comunicação', hoje 'Grau 18', lista os do grau 17;
# 'Grau 19' lista os do 18; 'Grau 28' os do 27; 'Grau 30' os do 29;
# Consistório: 'Grau 31' lista os do 30 e 'Grau 32' os do 31).
GRAU_ORIGEM_DA_ETAPA = {
    'pagamento': 8, 'iniciacao': 13, 'grau15': 14, 'comunicacao': 17,
    'grau19': 18, 'diploma': 21, 'grau28': 27, 'grau30': 29,
    'grau31': 30, 'grau32': 31,
}

# (grau âncora, meses mínimos desde o marco anterior) por listagem:
# entrar na relação do marco exige mais de X meses afetados ao grau âncora.
#   Grau 9  (Iniciação G9): 6+ meses desde o grau 4;
#   Grau 14: 3+ meses desde o grau 9;
#   Grau 15: 6+ meses desde o grau 14;
#   Grau 18: 6+ meses desde o grau 15;
#   Grau 19: 6+ meses desde o grau 18;
#   Grau 22 (ex-Diploma): 4+ meses desde o grau 19;
#   Grau 28: 4+ meses desde o grau 22;
#   Grau 30: 4+ meses desde o grau 28;
#   Grau 31: 6+ meses desde o grau 30;
#   Grau 32: 3+ meses desde o grau 31.
ANCORA_TEMPO_DA_ETAPA = {
    'pagamento': (4, 6),
    'iniciacao': (9, 3),
    'grau15': (14, 6),
    'comunicacao': (15, 6),
    'grau19': (18, 6),
    'diploma': (19, 4),
    'grau28': (22, 4),
    'grau30': (28, 4),
    'grau31': (30, 6),
    'grau32': (31, 3),
}


def _corpo_do_grau(numero):
    """Corpo do Rito responsável pelo grau (Perfeição 4º-14º, Capítulo 15º-18º etc.)."""
    if numero is None:
        return ''
    if numero <= 14:
        return 'perfeicao'
    if numero <= 18:
        return 'capitulo'
    if numero <= 30:
        return 'kadosh'
    if numero <= 32:
        return 'consistorio'
    return 'sc33'


CORPOS_RITO = [    {'valor': 'perfeicao',   'nome': 'Perfeição',  'faixa': '4º-14º',   'numeros': tuple(range(4, 15))},
    {'valor': 'capitulo',    'nome': 'Capítulo',   'faixa': '15º-18º',  'numeros': tuple(range(15, 19))},
    {'valor': 'kadosh',      'nome': 'Kadosh',     'faixa': '19º · 22º · 28º · 30º',  'numeros': (19, 22, 28, 30)},
    {'valor': 'consistorio', 'nome': 'Consistório', 'faixa': '31º-32º', 'numeros': (31, 32)},
    {'valor': 'sc33',        'nome': 'SC33',       'faixa': '33º',      'numeros': (33,)},
]


@web_login_required
def kanban(request):
    """Renderiza o quadro kanban com todas as colunas e cartoes."""
    ctx = _montar_contexto_kanban(request)
    return render(request, 'recepcao/kanban.html', ctx)


def _montar_contexto_kanban(request):
    """Monta o contexto completo para o template do kanban."""
    tid = tenant_id_da_sessao_ou_padrao(request)
    nicho = nicho_da_sessao(request)
    stages, stage_map = etapas_e_map_do_tenant(tid, nicho)

    # Filtros do card: Vale (id), Loja (nome) e Corpos do Rito (chips)
    prefeitura_filtro = request.GET.get('prefeitura', '').strip() or None
    loja_filtro = request.GET.get('loja', '').strip() or None
    vale_selecionado = _vale_do_filtro(prefeitura_filtro)
    corpos_escolhidos = _corpos_escolhidos(request)
    numeros_corpos = _numeros_de_corpos(corpos_escolhidos)

    negocios = _buscar_negocios(request)
    # Remove a coluna 'perdido' das stages antes de montar as colunas
    stages = [s for s in stages if s['key'] != 'perdido']
    colunas, _ = cards_do_kanban(negocios, stages)
    for col in colunas:
        col['grau'] = GRAU_DA_ETAPA.get(col['key'])
        col['corpo'] = _corpo_do_grau(col['grau'])
        col['grau_origem'] = GRAU_ORIGEM_DA_ETAPA.get(col['key'])

    # Passa Vale/Loja para filtrar candidatos
    cards_cand = cards_candidatos(
        tid,
        prefeitura=_padroes_prefeitura_candidato(
            vale_selecionado, prefeitura_filtro,
        ),
        loja=loja_filtro,
    )
    papel = (request.session.get('usuario') or {}).get('role', '')
    qtd_cand = _mesclar_candidatos(colunas, cards_cand, papel)
    # Colunas de grau listam automaticamente os membros do grau anterior;
    # com Corpos do Rito marcados (ou Loja com corpo definido), listam
    # apenas os marcos da faixa — sem depender de Vale e Loja
    corpo_da_loja = None if numeros_corpos else _corpo_da_loja_filtro(
        loja_filtro, vale_selecionado,
    )
    numeros_corpo_loja = None
    if corpo_da_loja is not None:
        numeros_corpo_loja = next(
            (
                c['numeros'] for c in CORPOS_RITO
                if c['valor'] == corpo_da_loja
            ),
            None,
        )
    cards_membros = _cards_membros_pela_etapa(
        request, prefeitura=prefeitura_filtro, loja=loja_filtro,
        numeros_marco=numeros_corpos or numeros_corpo_loja or None,
    )
    _mesclar_membros(colunas, cards_membros)
    qtd_lista = len(cards_membros)
    # Corpos marcados: o quadro fica restrito às colunas do corpo
    aviso_corpos = ''
    if corpos_escolhidos:
        restritas = [
            col for col in colunas
            if col.get('grau') is not None and col['grau'] in numeros_corpos
        ]
        if restritas:
            colunas = restritas
        else:
            aviso_corpos = 'Nenhuma coluna de grau pertence ao corpo selecionado.'
    # Filtro de Loja: só colunas do Corpo da Loja (Perfeição 4º-14º →
    # Grau 4/9/14; Capítulo 15º-18º → 15/18; Kadosh → 19/22/28/30; etc.)
    if corpo_da_loja is not None and numeros_corpo_loja:
        # As colunas da faixa do corpo ficam FIXAS, mesmo sem card
        # (Capítulo tem Grau 15 e 18; o 15 fica com 0 quando ninguém
        # do grau 14 está na loja)
        colunas = [
            col for col in colunas
            if col.get('grau') is not None
            and col['grau'] in numeros_corpo_loja
        ]
    # Com filtro de Vale/corpos ativo (sem Loja definindo a faixa), colunas
    # sem nenhum card somem do quadro
    if prefeitura_filtro or corpos_escolhidos or (
        loja_filtro and corpo_da_loja is None
    ):
        com_conteudo = [col for col in colunas if col['count'] > 0]
        if com_conteudo:  # segurança: nunca desaparecer o quadro inteiro
            colunas = com_conteudo
    ativos = [n for n in negocios if n.stage != 'perdido']

    # Busca prefeituras para o filtro
    prefeituras = _buscar_prefeituras(request)

    return {
        'colunas': colunas,
        'stages': stages,
        'stage_map': stage_map,
        'total_candidatos': len(ativos) + qtd_cand,
        'estagnados': _estagnados(ativos),
        'dias': _dias_do_request(request),
        'q': request.GET.get('q', ''),
        'origens': ORIGENS,
        'prefeituras': prefeituras,
        'prefeitura_filtro': prefeitura_filtro or '',
        'loja_filtro': loja_filtro or '',
        # Com um Vale escolhido, o select de Loja lista só as Lojas daquele Vale
        'lojas_filtro': _lojas_filtro(
            request, tid,
            vale_tenant_id=(
                vale_selecionado.tenant_id if vale_selecionado else None
            ),
        ),
        'corpos_rito': CORPOS_RITO,
        'corpos_escolhidos': corpos_escolhidos,
        'aviso_corpos': aviso_corpos,
        # Quantidade de irmãos selecionados pelos filtros (listagem/relatório)
        'qtd_lista': qtd_lista,
        'qs_filtro': request.GET.urlencode(),
    }


def _corpos_escolhidos(request):
    """Corpos do Rito marcados nos chips (GET `corpo`, múltiplos)."""
    validos = {corpo['valor'] for corpo in CORPOS_RITO}
    return [valor for valor in request.GET.getlist('corpo') if valor in validos]


def _numeros_de_corpos(corpos_escolhidos):
    """Graus de todas as colunas pertencentes aos corpos marcados."""
    numeros = set()
    for valor in corpos_escolhidos:
        for corpo in CORPOS_RITO:
            if corpo['valor'] == valor:
                numeros.update(corpo['numeros'])
                break
    return numeros


def _corpo_da_loja_filtro(loja_filtro, vale_selecionado=None):
    """Corpo do Rito da Loja selecionada no filtro (nome no GET).

    None quando não há loja escolhida ou o nome não existe; com um Vale
    selecionado, a busca fica restrita às Lojas daquele Vale.
    """

    if not loja_filtro:
        return None
    lojas = Loja.objects.filter(nome=loja_filtro)
    if vale_selecionado is not None:
        lojas = lojas.filter(tenant_id=vale_selecionado.tenant_id)
    return lojas.values_list('corpo', flat=True).first()


def _padroes_prefeitura_candidato(vale, prefeitura_filtro):
    """Padrões de busca de prefeitura para os cards de candidato.

    Candidatos guardam o Vale como id (string) ou nome; quando o Vale está
    resolvido, casamos pelas duas formas. Sem Vale: nenhum padrão (None).
    """
    if vale is None:
        return None
    return [str(vale.pk), vale.nome]


def _buscar_negocios(request):
    """Busca e filtra negocios do tenant (1 query, otimizado com Q)."""
    negocios = filtro_tenant(
        request,
        Negocio.objects.select_related('contato').prefetch_related('contato__tags'),
    )
    termo = request.GET.get('q', '').strip().lower()
    if termo:
        negocios = negocios.filter(
            Q(contato__nome__icontains=termo) |
            Q(contato__empresa__icontains=termo)
        )
    return list(negocios)


def _buscar_prefeituras(request):
    """Vales locais (banco local, mesma fonte de /membros/) para o filtro.

    admin_saas/ADM veem os Vales de todos os tenants; os demais papéis veem
    apenas os Vales do tenant efetivo da sessão.
    """

    papel = (request.session.get('usuario') or {}).get('role', '')
    vales = Vale.objects.filter(status='ATIVA')
    if papel not in ('admin_saas', 'ADM'):
        tenant_id = tenant_id_da_sessao_ou_padrao(request)
        if tenant_id is None:
            return []
        vales = vales.filter(tenant_id=tenant_id)
    return [
        {'id': str(vale.pk), 'nome': vale.nome}
        for vale in vales.order_by('nome', 'id')
    ]


def _lojas_filtro(request, tid, vale_tenant_id=None):
    """Lojas locais para o filtro, agrupadas pelo Corpo do Rito.

    Com um Vale selecionado (vale_tenant_id), lista apenas as Lojas daquele
    Vale — ainda dentro do escopo do papel. Cada grupo traz o rótulo do
    corpo com a sua faixa de graus (Perfeição 4º-14º, Capítulo 15º-18º,
    Kadosh 19º/22º/28º/30º, Consistório 31º-32º, SC33 33º).
    """

    papel = (request.session.get('usuario') or {}).get('role', '')
    lojas = Loja.objects.filter(situacao='ATIVA')
    if papel not in ('admin_saas', 'ADM'):
        if tid is None:
            return []
        lojas = lojas.filter(tenant_id=tid)
    if vale_tenant_id is not None:
        lojas = lojas.filter(tenant_id=vale_tenant_id)

    vistos = set()
    por_corpo = {corpo['valor']: [] for corpo in CORPOS_RITO}
    for loja in lojas.order_by('nome', 'id'):
        if not loja.nome or loja.nome in vistos:
            continue  # mesmo nome entre tenants entra uma única vez
        vistos.add(loja.nome)
        if loja.corpo in por_corpo:
            por_corpo[loja.corpo].append({'nome': loja.nome})

    return [
        {
            'rotulo': f"{corpo['nome']} · {corpo['faixa']}",
            'lojas': itens,
        }
        for corpo in CORPOS_RITO
        for itens in (por_corpo[corpo['valor']],)
        if itens
    ]


def _mesclar_candidatos(colunas, cards_cand, papel=''):
    """Distribui os cards de candidatos pelas colunas do kanban.

    A coluna segue o nível de revisão atual (DM/vazio → 'suplica';
    aprovado pelo Delegado → 'prefeito', etc.). Também filtra a
    visibilidade pelo papel: após a aprovação do Delegado, só o
    Prefeito, o oficial do nível e o Admin continuam vendo o card.

    Retorna quantos cards foram adicionados.
    """
    if not cards_cand:
        return 0
    from candidatos.oficialato import pode_ver_candidato

    chaves = {col['key'] for col in colunas}
    por_coluna = {}
    adicionados = 0
    for card in cards_cand:
        if papel and not pode_ver_candidato(card.get('revisao'), papel):
            continue
        alvo = card.get('coluna') or 'suplica'
        if alvo not in chaves:
            alvo = 'suplica'
        por_coluna.setdefault(alvo, []).append(card)
        adicionados += 1

    for col in colunas:
        novos = por_coluna.get(col['key'])
        if novos:
            col['cards'] = novos + col['cards']
            col['count'] += len(novos)
    return adicionados


def _vale_do_filtro(prefeitura_filtro):
    """Vale selecionado no filtro (o select envia o id do Vale).

    None quando vazio; None também para id inválido (o chamador decide
    se ignora ou devolve listagem vazia).
    """

    if not prefeitura_filtro:
        return None
    try:
        return Vale.objects.get(pk=int(prefeitura_filtro))
    except (Vale.DoesNotExist, TypeError, ValueError):
        return None


def _cards_membros_pela_etapa(request, prefeitura=None, loja=None,
                              numeros_marco=None):
    """Cards de membro pelas colunas de grau (detentores do grau anterior).

    Regra de entrada na listagem (marco M):
      1) grau atual (maior conquistado) = grau imediatamente anterior ao marco
         (GRAU_ORIGEM_DA_ETAPA: G9←8, G14←13, G15←14, G18←17, G19←18, G22←21,
         G28←27, G30←29);
      2) tempo mínimo afetado ao grau âncora (ANCORA_TEMPO_DA_ETAPA):
         a data do grau âncora tem de ser anterior a hoje menos X meses.
    "Todos" é literal: ativos e inativos, sem filtro de situação.
    Escopo por papel: admin_saas/ADM veem todos os tenants, os demais papéis
    apenas o tenant efetivo da sessão.
    Filtros do card (GET): `prefeitura` (id do Vale → membro do tenant do
    Vale) e `loja` (nome da Loja → membro vinculado à Loja; quando um Vale
    está selecionado, só Lojas daquele Vale entram). `numeros_marco`: quando
    informado (chips de Corpos do Rito), só entram membros cujo marco de
    destino pertence aos corpos marcados — sem depender de Vale ou Loja.
    """
    from dateutil.relativedelta import relativedelta

    from contatos.views.gprb_membros import _tenant_ids_para_lista
    from tarefas.presencas import PresencaServico

    hoje = timezone.localdate()
    limite_por_ancora = {
        ancora: hoje - relativedelta(months=meses)
        for ancora, meses in ANCORA_TEMPO_DA_ETAPA.values()
    }
    etapa_por_grau = {
        grau: etapa for etapa, grau in GRAU_ORIGEM_DA_ETAPA.items()
    }
    # Marco de destino de cada grau de origem (ex.: 8 → 9, 31 → 32)
    marco_por_grau = {
        grau: GRAU_DA_ETAPA[etapa] for grau, etapa in etapa_por_grau.items()
    }

    tenants = _tenant_ids_para_lista(request)
    qs = Membro.objects.all()
    if tenants:
        qs = qs.filter(tenant_id__in=tenants)
    # Filtros do card: Vale (→ tenant) e Loja (nome, restrita ao Vale)
    vale = _vale_do_filtro(prefeitura)
    if prefeitura and vale is None:
        return []  # id de Vale inválido → nada entra no quadro
    if vale is not None:
        qs = qs.filter(tenant_id=vale.tenant_id)
    if loja:
        lojas_da_escolha = Loja.objects.filter(nome=loja)
        if vale is not None:
            lojas_da_escolha = lojas_da_escolha.filter(tenant_id=vale.tenant_id)
        ids_loja = list(lojas_da_escolha.values_list('pk', flat=True))
        if not ids_loja:
            return []
        qs = qs.filter(lojas__pk__in=ids_loja).distinct()
    membros = list(
        qs.annotate(grau_atual=Max('graus__grau__numero'))
        .filter(grau_atual__in=set(GRAU_ORIGEM_DA_ETAPA.values()))
        .prefetch_related('lojas')
        .order_by('nome', 'id')
    )
    # Datas de TODOS os graus de cada membro (âncora p/ tempo e último grau)
    datas_graus = {}
    if membros:
        mids = [m.pk for m in membros]
        for membro_id, numero, data in (
            GrauMembro.objects.filter(membro_id__in=mids)
            .values_list('membro_id', 'grau__numero', 'data')
        ):
            datas_graus.setdefault(membro_id, {})[numero] = data

    # Presença percentual de todos os candidatos (1 query agregada)
    percentuais = PresencaServico.percentuais(membros)

    cards = []
    for m in membros:
        marco = marco_por_grau[m.grau_atual]
        # Corpos do Rito marcados: só membros cujo marco pertence ao corpo
        if numeros_marco and marco not in numeros_marco:
            continue
        datas_do_membro = datas_graus.get(m.pk, {})
        ancora = ANCORA_TEMPO_DA_ETAPA[etapa_por_grau[m.grau_atual]][0]
        data_ancora = datas_do_membro.get(ancora)
        # Entrada exige mais de X meses do grau âncora
        if data_ancora is None or data_ancora > limite_por_ancora[ancora]:
            continue
        lojas = [loja.nome for loja in m.lojas.all()[:2]]
        presenca = percentuais.get(m.pk)
        cards.append({
            'id': m.pk,
            'tipo': 'membro',
            'nome': m.nome,
            'grau_at': m.grau_atual,
            'situacao': m.situacao,
            'loja_label': ', '.join(lojas),
            # Sem chamada registrada conta como 0%
            'presenca': 0 if presenca is None else presenca,
            # Extras para o relatório (listagem em PDF/Excel)
            'cadastro': m.cadastro_numero,
            'data_ultimo_grau': datas_do_membro.get(m.grau_atual),
        })
    return cards


def _mesclar_membros(colunas, cards):
    """Distribui os cards de membro pelas colunas de grau correspondentes.

    O destino é o mapa GRAU_ORIGEM_DA_ETAPA (grau atual do membro → coluna do
    próximo marco). Retorna quantos cards foram adicionados.
    """
    if not cards:
        return 0
    coluna_por_grau = {grau: etapa for etapa, grau in GRAU_ORIGEM_DA_ETAPA.items()}

    por_coluna = {}
    for card in cards:
        alvo = coluna_por_grau.get(card['grau_at'])
        if alvo:
            por_coluna.setdefault(alvo, []).append(card)

    adicionados = 0
    for col in colunas:
        novos = por_coluna.get(col['key'])
        if novos:
            col['cards'] = col['cards'] + novos
            col['count'] += len(novos)
            adicionados += len(novos)
    return adicionados


def _estagnados(ativos):
    """Retorna negocios estagnados (sem movimentacao ha X dias)."""
    return estagnados_da_lista(ativos, _dias_do_request(ativos[0] if ativos else None))


def _dias_do_request(request):
    """Extrai e valida o parametro 'dias' do request."""
    if request is None:
        return 7
    raw = request.GET.get('dias', '') if hasattr(request, 'GET') else ''
    dias = int(raw) if raw.isdigit() else 7
    return max(1, min(dias, 90))


@web_login_required
@web_requer_tenant_context
def mover(request, pk):
    """Move um NEGOCIO (deal) de etapa — pk e o id do negocio."""
    if request.method != 'POST':
        return HttpResponseBadRequest('Metodo nao permitido.')
    if not pode_editar(request):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return HttpResponseForbidden('Somente leitura.')
        return redirect('recepcao:kanban')

    stage = request.POST.get('stage', '')
    if stage not in etapa_map_do_tenant(tenant_id_da_sessao(request), nicho_da_sessao(request)):
        return HttpResponseBadRequest('Etapa invalida.')

    negocio = get_object_or_404(filtro_tenant(request, Negocio.objects.all()), pk=pk)
    if negocio.stage != stage:
        _mover_negocio(negocio, stage, request)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(dados_board(request))
    return redirect('recepcao:kanban')


def _mover_negocio(negocio, stage, request):
    """Move o negocio para a nova etapa e dispara side-effects."""
    from automacoes.engine import disparar

    de_etapa = negocio.stage
    registrar_movimentacao(negocio, de_etapa, stage, request.session.get('usuario_id'))
    negocio.stage = stage
    negocio.save(update_fields=['stage', 'updated_at'])

    if stage == 'fechado':
        from emails.servico import marcar_conversoes
        marcar_conversoes(negocio.contato)

    disparar(
        'negocio_movido',
        tenant_id=tenant_id_da_sessao(request),
        contato=negocio.contato,
        negocio=negocio,
        de_etapa=de_etapa,
        para_etapa=stage,
    )
    atualizar_score(negocio.contato)


@web_login_required
@web_requer_tenant_context
def excluir_negocio(request, pk):
    """Exclui um NEGOCIO (deal) do funil — pk e o id do negocio (AJAX POST)."""
    if request.method != 'POST':
        return HttpResponseBadRequest('Metodo nao permitido.')
    if not pode_editar(request):
        return JsonResponse({'ok': False, 'erro': 'Sem permissao.'}, status=403)
    negocio = get_object_or_404(filtro_tenant(request, Negocio.objects.all()), pk=pk)
    negocio.delete()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'colunas': dados_board(request)['colunas']})
    return redirect('recepcao:kanban')


def _monta_descritor_relatorio(corpos_escolhidos, loja_filtro, vale):
    """Contexto de descrição do relatório (corpos, loja e vale)."""
    return {
        'corpos': [
            corpo['nome'] for corpo in CORPOS_RITO
            if corpo['valor'] in corpos_escolhidos
        ],
        'loja': loja_filtro or '',
        'vale': vale.nome if vale is not None else '',
    }


def _dados_do_relatorio(request):
    """Listagem dos irmãos selecionados pelos filtros do Flow de Iniciação.

    Mesmos filtros e mesmas regras do quadro (cadeia + tempo mínimo; corpos
    do Rito independem de Vale/Loja; Loja restringe aos seus vinculados e
    fixa a faixa do seu corpo).
    """
    prefeitura_filtro = request.GET.get('prefeitura', '').strip() or None
    loja_filtro = request.GET.get('loja', '').strip() or None
    vale_selecionado = _vale_do_filtro(prefeitura_filtro)
    corpos_escolhidos = _corpos_escolhidos(request)
    numeros_marco = _numeros_de_corpos(corpos_escolhidos) or None
    if not numeros_marco:
        corpo_loja = _corpo_da_loja_filtro(loja_filtro, vale_selecionado)
        if corpo_loja is not None:
            numeros = next(
                (
                    c['numeros'] for c in CORPOS_RITO
                    if c['valor'] == corpo_loja
                ),
                None,
            )
            numeros_marco = set(numeros) if numeros else None
    cards = _cards_membros_pela_etapa(
        request, prefeitura=prefeitura_filtro, loja=loja_filtro,
        numeros_marco=numeros_marco,
    )
    linhas = sorted(
        (
            {
                'cadastro': card['cadastro'],
                'nome': card['nome'],
                'grau': card['grau_at'],
                'data_ultimo': card['data_ultimo_grau'],
                'presenca': card['presenca'],
            }
            for card in cards
        ),
        key=lambda linha: linha['nome'],
    )
    descritor = _monta_descritor_relatorio(
        corpos_escolhidos, loja_filtro, vale_selecionado,
    )
    return linhas, descritor


@web_login_required
def relatorio(request):
    """Listagem (relatório) dos irmãos selecionados pelos filtros."""
    linhas, descritor = _dados_do_relatorio(request)
    return render(request, 'recepcao/relatorio.html', {
        'linhas': linhas,
        'descritor': descritor,
        'qs_filtro': request.GET.urlencode(),
    })


_MIMES_RELATORIO_INICIACAO = {
    'pdf': 'application/pdf',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
}


@web_login_required
@require_GET
def relatorio_exportar(request, formato):
    """Download do relatório de iniciação em PDF ou Excel."""
    if formato not in _MIMES_RELATORIO_INICIACAO:
        return HttpResponseBadRequest('Formato de relatório inválido.')
    linhas, descritor = _dados_do_relatorio(request)
    gerado_em = timezone.localdate()
    if formato == 'pdf':
        conteudo = gerar_pdf_iniciacao(linhas, descritor, gerado_em)
    else:
        conteudo = gerar_xlsx_iniciacao(linhas, descritor, gerado_em)
    resposta = HttpResponse(
        conteudo, content_type=_MIMES_RELATORIO_INICIACAO[formato],
    )
    resposta['Content-Disposition'] = (
        f'attachment; filename="iniciacao-{gerado_em.isoformat()}.{formato}"'
    )
    return resposta
