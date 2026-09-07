"""View principal do kanban — renderizacao, mover e excluir negocios.

Otimizado para performance:
  - Imports no topo do modulo
  - Busca OR com Q objects
  - Passa qtd_cand para evitar query duplicada
"""

from django.db.models import Q
from django.http import HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from acesso.decorators import (
    filtro_tenant,
    nicho_da_sessao,
    pode_editar,
    tenant_id_da_sessao,
    web_login_required,
    web_requer_edicao,
)
from contatos.models import Negocio, registrar_movimentacao
from contatos.scoring import atualizar_score
from core.dominio import ORIGENS
from recepcao.models import etapa_map_do_tenant, etapas_e_map_do_tenant
from recepcao.views.board import dados_board
from recepcao.views.helpers import (
    cards_candidatos,
    cards_do_kanban,
    estagnados_da_lista,
    tenant_id_da_sessao_ou_padrao,
)


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

    # Filtro de prefeitura
    prefeitura_filtro = request.GET.get('prefeitura', '').strip() or None

    negocios = _buscar_negocios(request)
    # Remove a coluna 'perdido' das stages antes de montar as colunas
    stages = [s for s in stages if s['key'] != 'perdido']
    colunas, _ = cards_do_kanban(negocios, stages)

    # Passa prefeitura para filtrar candidatos
    cards_cand = cards_candidatos(tid, prefeitura=prefeitura_filtro)
    papel = (request.session.get('usuario') or {}).get('role', '')
    qtd_cand = _mesclar_candidatos(colunas, cards_cand, papel)
    ativos = [n for n in negocios if n.stage != 'perdido']

    # Busca prefeituras para o filtro
    prefeituras = _buscar_prefeituras()

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
    }


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


def _buscar_prefeituras():
    """Busca prefeituras GPRB para o filtro (com cache)."""
    from django.core.cache import cache

    cache_key = 'recepcao_prefeituras_filtro'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        from core.gprb import opcoes_prefeituras_usuario
        prefeituras = opcoes_prefeituras_usuario()
    except Exception:
        prefeituras = []

    cache.set(cache_key, prefeituras, timeout=300)  # 5 minutos
    return prefeituras


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
