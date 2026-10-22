"""Views web do Dashboard — KPIs, timeline, conversao, funil, recentes e analises avancadas."""

import html
import logging
from datetime import date, datetime, time, timedelta

from django.db import Error as DBError
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from acesso.decorators import filtro_tenant, nicho_da_sessao, web_login_required
from acesso.models import MetaVendedor, Tenant, Usuario
from contatos.models import Movimentacao, Negocio, Nota
from core.dominio import ORIGENS, PESOS_ETAPA, SEGS
from core.gprb import anuidade_ano_referencia
from core.utils import brl as _brl
from core.utils import brl_curto as _brl_curto
from core.utils import iniciais as _iniciais
from dashboard.repositories.local_repository import LocalRepository
from dashboard.services.cache_service import DashboardCache, DjangoCacheBackend
from recepcao.models import etapa_map_do_tenant, etapas_do_tenant
from tarefas.models import Tarefa

logger = logging.getLogger(__name__)

# _brl, _brl_curto, _iniciais → importados de core.utils


def _shade(hex_color, factor):
    """Escurece/clareia uma cor hex por um fator (-1..1) — pra face 3D."""
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def mix(c):
        if factor < 0:
            return round(c * (1 + factor))
        return round(c + (255 - c) * factor)

    def h2(v):
        v = max(0, min(255, v))
        s = format(v, 'x')
        return s if len(s) == 2 else '0' + s

    return '#' + h2(mix(r)) + h2(mix(g)) + h2(mix(b))


def _esc_attr(v):
    """Escapa um valor para interpolar com seguranca em SVG (atributos e texto)."""
    return html.escape(str(v), quote=True)


def _funnel_svg(funil, *, color_map=None, id_prefix='f3g'):
    """Gráfico de funil 3D em SVG — unificado para funil de vendas e BAII.

    Args:
        funil: lista de dicts com 'count' e 'color'.
        color_map: dict {índice: cor_hex} que sobrepõe s['color'].
                   Usado pelo BAII para aplicar o tema azul (GEOD-CEOD).
        id_prefix: prefixo para IDs de gradientes SVG (evita colisão).
    """
    steps = list(funil)
    if not steps:
        return ''
    W, sliceH, gap, depthX, depthY, topY = 340, 62, 5, 22, 14, 16
    cx, n = W / 2, len(steps)
    shadowY = topY + n * (sliceH + gap) + depthY + 10
    max_half = cx * 0.92

    defs = '<defs>'
    for i, s in enumerate(steps):
        cor = (color_map.get(i, s['color']) if color_map else s['color'])
        dark = _shade(cor, -0.42)
        defs += (f'<linearGradient id="{id_prefix}g{i}" x1="0" y1="0" x2="0" y2="1">'
                 f'<stop offset="0%" stop-color="{_esc_attr(cor)}" stop-opacity="0.98"/>'
                 f'<stop offset="100%" stop-color="{_esc_attr(dark)}" stop-opacity="0.9"/></linearGradient>')
        defs += (f'<linearGradient id="{id_prefix}s{i}" x1="0" y1="0" x2="1" y2="0">'
                 f'<stop offset="0%" stop-color="{_esc_attr(dark)}" stop-opacity="0.78"/>'
                 f'<stop offset="100%" stop-color="{_esc_attr(dark)}" stop-opacity="0.32"/></linearGradient>')
    defs += '</defs>'

    c = defs
    c += (f'<ellipse cx="{(cx + depthX * 0.4):.1f}" cy="{shadowY:.1f}" '
          f'rx="{(cx * 0.5):.1f}" ry="{(depthY * 0.9):.1f}" fill="rgba(0,0,0,0.4)"/>')

    for i, s in enumerate(steps):
        cor = (color_map.get(i, s['color']) if color_map else s['color'])
        frac_top = 1 - (i / n) * 0.82
        frac_bot = 1 - ((i + 1) / n) * 0.82
        w_top, w_bot = frac_top * max_half, frac_bot * max_half
        y1 = topY + i * (sliceH + gap)
        y2 = y1 + sliceH
        fl, fr = cx - w_top, cx + w_top
        nl, nr = cx - w_bot, cx + w_bot

        c += (f'<polygon points="{fl:.1f},{y1:.1f} {fr:.1f},{y1:.1f} {nr:.1f},{y2:.1f} {nl:.1f},{y2:.1f}" '
              f'fill="url(#{id_prefix}g{i})"/>')
        c += (f'<polygon points="{fr:.1f},{y1:.1f} {fr + depthX:.1f},{y1 - depthY:.1f} '
              f'{nr + depthX:.1f},{y2 - depthY:.1f} {nl:.1f},{y2:.1f}" fill="url(#{id_prefix}s{i})"/>')
        c += (f'<line x1="{fl:.1f}" y1="{y1:.1f}" x2="{fr:.1f}" y2="{y1:.1f}" '
              f'stroke="rgba(255,255,255,0.24)" stroke-width="1.2"/>')
        c += (f'<text x="{cx:.1f}" y="{(y1 + sliceH / 2 + 4):.1f}" text-anchor="middle" font-size="14" '
              f'font-weight="700" font-family="JetBrains Mono, monospace" fill="#fff" opacity="0.92">{s["count"]}</text>')
        if i == 0:
            ecx = (fl + fr + depthX) / 2
            erx = (fr + depthX - fl) / 2
            c += (f'<ellipse cx="{ecx:.1f}" cy="{y1:.1f}" rx="{erx:.1f}" ry="{depthY * 0.75:.1f}" '
                  f'fill="{_esc_attr(cor)}" opacity="0.95"/>')
            c += (f'<ellipse cx="{ecx:.1f}" cy="{y1:.1f}" rx="{erx:.1f}" ry="{depthY * 0.75:.1f}" '
                  f'fill="none" stroke="#74b3c6" stroke-width="1.4" opacity="0.6"/>')

    return f'<svg viewBox="0 0 {W} {shadowY + 8}" class="w-full">' + c + '</svg>'


_BAII_COLORS = ['#1a5fb4', '#3b7ded', '#93b8f7']  # base -> topo


def _para_svg_pyramide(faixas):
    """Shape de renderização das faixas, recebidas na ordem base → topo."""
    itens = [
        {
            'name': faixa['name'], 'label': faixa['label'],
            'count': faixa['total'],
        }
        for faixa in faixas
    ]
    total = sum(i['count'] for i in itens) or 1
    n = len(itens)
    for k, i in enumerate(itens):
        i['pct'] = round(i['count'] / total * 100)
        # k=0 (faixa da base) = azul profundo; topo = azul claro
        cor_idx = round(k / max(n - 1, 1) * (len(_BAII_COLORS) - 1))
        i['color'] = _BAII_COLORS[cor_idx]
    return itens


def _pyramide_svg(itens):
    """Pirâmide 3D: recebe faixas da base ao topo e desenha o ápice primeiro.

    A largura representa a posição da faixa, não a quantidade de membros.
    Os totais e nomes são exibidos dentro de cada fatia.
    """
    if not itens:
        return ''
    steps = list(itens)[::-1]  # topo -> base: menos membros primeiro
    n = len(steps)
    W, sliceH, gap, depthX, depthY, topY = 340, 62, 5, 22, 14, 16
    min_frac = 0.18
    cx = W / 2
    shadowY = topY + n * (sliceH + gap) + depthY + 10
    max_half = cx * 0.92

    def _meia_largura(pos):
        # pos 0..n: 0 = topo estreito, n = base larga
        return max_half * (min_frac + (1 - min_frac) * pos / n)

    defs = '<defs>'
    for i, s in enumerate(steps):
        cor = s['color']
        dark = _shade(cor, -0.42)
        defs += (f'<linearGradient id="bairiG{i}" x1="0" y1="0" x2="0" y2="1">'
                 f'<stop offset="0%" stop-color="{_esc_attr(cor)}" stop-opacity="0.98"/>'
                 f'<stop offset="100%" stop-color="{_esc_attr(dark)}" stop-opacity="0.9"/></linearGradient>')
        defs += (f'<linearGradient id="bairiS{i}" x1="0" y1="0" x2="1" y2="0">'
                 f'<stop offset="0%" stop-color="{_esc_attr(dark)}" stop-opacity="0.78"/>'
                 f'<stop offset="100%" stop-color="{_esc_attr(dark)}" stop-opacity="0.32"/></linearGradient>')
    defs += '</defs>'

    c = defs
    c += (f'<ellipse cx="{(cx + depthX * 0.4):.1f}" cy="{shadowY:.1f}" '
          f'rx="{(cx * 0.5):.1f}" ry="{(depthY * 0.9):.1f}" fill="rgba(0,0,0,0.4)"/>')

    for i, s in enumerate(steps):
        cor = s['color']
        w_top = _meia_largura(i)
        w_bot = _meia_largura(i + 1)
        y1 = topY + i * (sliceH + gap)
        y2 = y1 + sliceH
        fl, fr = cx - w_top, cx + w_top
        nl, nr = cx - w_bot, cx + w_bot

        c += (f'<polygon points="{fl:.1f},{y1:.1f} {fr:.1f},{y1:.1f} {nr:.1f},{y2:.1f} {nl:.1f},{y2:.1f}" '
              f'fill="url(#bairiG{i})"/>')
        c += (f'<polygon points="{fr:.1f},{y1:.1f} {fr + depthX:.1f},{y1 - depthY:.1f} '
              f'{nr + depthX:.1f},{y2 - depthY:.1f} {nl:.1f},{y2:.1f}" fill="url(#bairiS{i})"/>')
        c += (f'<line x1="{fl:.1f}" y1="{y1:.1f}" x2="{fr:.1f}" y2="{y1:.1f}" '
              f'stroke="rgba(255,255,255,0.24)" stroke-width="1.2"/>')
        c += (f'<text x="{cx:.1f}" y="{(y1 + sliceH / 2 - 3):.1f}" text-anchor="middle" font-size="10" '
              f'font-weight="600" font-family="Manrope, sans-serif" fill="#f4fafb" opacity="0.9">'
              f'{_esc_attr(s["name"])}</text>')
        c += (f'<text x="{cx:.1f}" y="{(y1 + sliceH / 2 + 15):.1f}" text-anchor="middle" font-size="14" '
              f'font-weight="700" font-family="JetBrains Mono, monospace" fill="#fff" opacity="0.96">'
              f'{s["count"]}</text>')
        if i == n - 1:
            # "boca" 3D embaixo da base larga (invertendo a do funil)
            ecx = (nl + nr + depthX) / 2
            erx = (nr - nl + depthX) / 2
            ecy = y2 + depthY * 0.45
            c += (f'<ellipse cx="{ecx:.1f}" cy="{ecy:.1f}" rx="{erx:.1f}" ry="{depthY * 0.6:.1f}" '
                  f'fill="{_esc_attr(cor)}" opacity="0.9"/>')

    return f'<svg viewBox="0 0 {W} {shadowY + 8}" class="w-full">' + c + '</svg>'


def _timeline_svg(timeline):
    """Gráfico de linha dos últimos 30 dias — mesmo visual do index.html original."""
    days = list(timeline)
    if not days:
        return ''
    mx = max([d['valor'] for d in days] + [1])
    W, H, pad_x, pad_t, pad_b = 660, 190, 28, 22, 30
    n = len(days)
    pts = []
    for i, d in enumerate(days):
        x = pad_x + (i / (n - 1)) * (W - pad_x * 2)
        y = (H - pad_b) - (d['valor'] / mx) * (H - pad_t - pad_b)
        pts.append((x, y, d))

    path = ' '.join(('M' if i == 0 else 'L') + f'{p[0]:.1f} {p[1]:.1f}' for i, p in enumerate(pts))
    area = path + f' L{pts[-1][0]:.1f} {H - pad_b} L{pts[0][0]:.1f} {H - pad_b} Z'

    labels = ''
    for i, p in enumerate(pts):
        if i % 5 == 0 or i == n - 1:
            labels += (f'<text x="{p[0]:.1f}" y="{H - 8}" text-anchor="middle" font-size="9.5" '
                       f'font-family="JetBrains Mono, monospace" fill="#6f8a93">{p[2]["data"]}</text>')
    dots = ''
    for p in pts:
        if p[2]['valor'] > 0:
            dots += (f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="3" fill="#74b3c6" stroke="#0b2029" '
                     f'stroke-width="1"><title>{p[2]["valor"]} contatos em {p[2]["data"]}</title></circle>')

    return (f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" class="w-full min-w-[520px]">'
            '<defs>'
            '<linearGradient id="tlArea" x1="0" y1="0" x2="0" y2="1">'
            '<stop offset="0%" stop-color="#74b3c6" stop-opacity="0.25"/>'
            '<stop offset="100%" stop-color="#74b3c6" stop-opacity="0"/></linearGradient>'
            '<filter id="tlGlow" x="-50%" y="-50%" width="200%" height="200%">'
            '<feGaussianBlur stdDeviation="2.2" result="b"/>'
            '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
            '</defs>'
            f'<path d="{area}" fill="url(#tlArea)"/>'
            f'<path d="{path}" fill="none" stroke="#74b3c6" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round" filter="url(#tlGlow)"/>'
            + dots + labels + '</svg>')


def _resumo(request, negocios=None):
    """Números de cabeçalho do dashboard — usados pela página e pelo auto-refresh JSON."""
    if negocios is None:
        negocios = filtro_tenant(request, Negocio.objects.select_related('contato'))
    hoje = date.today()
    inicio_mes = timezone.make_aware(datetime.combine(hoje.replace(day=1), time.min))
    inicio30 = timezone.make_aware(datetime.combine(hoje - timedelta(days=30), time.min))

    ativos = negocios.exclude(stage__in=['perdido', 'fechado'])
    fechados_mes = negocios.filter(stage='fechado', updated_at__gte=inicio_mes)
    nao_perdidos = negocios.exclude(stage='perdido')

    valor_funil = ativos.aggregate(s=Sum('valor'))['s'] or 0
    valor_fechados_mes = fechados_mes.aggregate(s=Sum('valor'))['s'] or 0
    conv = round(fechados_mes.count() / nao_perdidos.count() * 100) if nao_perdidos.count() else 0

    # Receita projetada: pipeline ponderado por etapa (peso do tenant; fallback do nicho)
    tid = request.session.get('usuario', {}).get('tenant_id')
    mapa_etapas = etapa_map_do_tenant(tid, nicho_da_sessao(request))

    def _peso(stage):
        return float(mapa_etapas.get(stage, {}).get('peso', PESOS_ETAPA.get(stage, 0)))

    projetado = sum(float(n.valor) * _peso(n.stage) for n in nao_perdidos)
    valor_aberto = float(ativos.aggregate(s=Sum('valor'))['s'] or 0)
    projetado_aberto = sum(float(n.valor) * _peso(n.stage) for n in ativos)
    pct_potencial = round(projetado_aberto / valor_aberto * 100) if valor_aberto else 0

    # Tempo médio de fechamento (dias, do created_at ao updated_at dos fechados no mês)
    tempos = [(f.updated_at - f.created_at).total_seconds() / 86400 for f in fechados_mes]
    tempo_medio = sum(tempos) / len(tempos) if tempos else None

    # Meta mensal do tenant
    tid = request.session.get('usuario', {}).get('tenant_id')
    meta = Tenant.objects.filter(pk=tid).values_list('meta_mensal', flat=True).first() if tid else None
    meta_valor = float(meta) if meta else None
    meta_pct = round(float(valor_fechados_mes) / meta_valor * 100) if meta_valor else None
    meta_bar_pct = min(100, meta_pct) if meta_pct is not None else None

    # ---- KPIs de Lojas/Membros (banco local) ----
    ano_corrente = hoje.year
    tid_local = request.session.get('usuario', {}).get('tenant_id')
    try:
        local = LocalRepository(tid_local).dashboard_kpis(ano=ano_corrente)
    except DBError as e:
        logger.error('Erro nos KPIs locais do dashboard: %s', e)
        local = {}
    lojas_ativas = local.get('lojas_ativas', 0)
    lojas_total = local.get('lojas_total', 0)
    membros_ativos = local.get('membros_ativos', 0)
    membros_total = local.get('membros_total', 0)
    novos_membros = local.get('novos_membros_ano', 0)

    return {
        'ativos': ativos.count(),
        'novos_mes': negocios.filter(created_at__gte=inicio_mes).count(),
        'ultimos30': negocios.filter(created_at__gte=inicio30).count(),
        'valor_funil': _brl_curto(valor_funil),
        'fechados_qtd': fechados_mes.count(),
        'valor_fechados': _brl(valor_fechados_mes),
        'conversao': f'{conv}%',
        'receita_projetada': _brl_curto(projetado),
        'projetado_pct': pct_potencial,
        'tempo_medio_fechamento': f'{tempo_medio:.1f}' if tempo_medio is not None else '—',
        'meta_valor': _brl(meta_valor) if meta_valor is not None else None,
        'meta_pct': meta_pct,
        'meta_bar_pct': meta_bar_pct,
        # Lojas/Membros (banco local)
        'lojas_ativas': lojas_ativas,
        'lojas_total': lojas_total,
        'membros_ativos': membros_ativos,
        'membros_total': membros_total,
        'novos_membros': novos_membros,
    }


@web_login_required
def dados(request):
    """Auto-refresh leve: numeros do cabecalho em JSON para o polling do dashboard."""
    tid = request.session.get('usuario', {}).get('tenant_id')
    nicho = nicho_da_sessao(request)
    dashboard_cache = DashboardCache(DjangoCacheBackend())
    cached = dashboard_cache.get_kpis(tid, nicho)
    if cached is not None:
        resumo = cached['resumo']
    else:
        negocios = filtro_tenant(request, Negocio.objects.select_related('contato'))
        resumo = _resumo(request, negocios)
    resumo['atualizado_em'] = timezone.localtime().strftime('%H:%M:%S')
    return JsonResponse(resumo)


@web_login_required
def anuidade_dados(request):
    """JSON do card Anuidade — recorte por Potencia (prefeitura) e/ou Loja.

    O percentual segue pagantes/pendentes do recorte; `total` e a soma
    simples das lojas do escopo (membro em 2 lojas soma 2).
    """
    prefeitura_id = request.GET.get('potencia') or None
    loja_id = request.GET.get('loja') or None
    tid = request.session.get('usuario', {}).get('tenant_id')
    try:
        dados_card = LocalRepository(tid).anuidade_card(
            anuidade_ano_referencia(), prefeitura_id=prefeitura_id, loja_id=loja_id)
    except DBError as e:
        logger.error('Erro no endpoint anuidade_dados: %s', e)
        dados_card = {'pagantes': 0, 'pendentes': 0, 'total': 0,
                      'percentual': 0, 'lojas': []}
    return JsonResponse(dados_card)




# ---------------------------------------------------------------------------
# Helpers extraidos de index() - cada um calcula um bloco do dashboard
# ---------------------------------------------------------------------------

def _calcular_timeline(negocios, hoje):
    """Monta timeline dos ultimos 30 dias (query unica com annotate)."""
    inicio = hoje - timedelta(days=29)
    agg = (
        negocios.filter(created_at__date__gte=inicio)
        .annotate(dia=TruncDate('created_at'))
        .values('dia')
        .annotate(count=Count('id'))
        .order_by('dia')
    )
    por_dia = {r['dia']: r['count'] for r in agg}
    timeline = []
    d = inicio
    while d <= hoje:
        timeline.append({'data': f'{d.day:02d}/{d.month:02d}', 'valor': por_dia.get(d, 0)})
        d += timedelta(days=1)
    return timeline, max([p['valor'] for p in timeline] + [1])


def _calcular_conversao(stages, ocorrencias):
    """Taxa de conversao entre pares consecutivos de etapas."""
    st_validos = [s for s in stages if s['key'] != 'perdido']
    conversao = []
    for i in range(1, len(st_validos)):
        prev, cur = st_validos[i - 1], st_validos[i]
        pct = round(cur and (ocorrencias[cur['key']] / ocorrencias[prev['key']] * 100)) if ocorrencias[prev['key']] else 0
        conversao.append({
            'de': prev['name'], 'para': cur['name'],
            'cor': cur['color'], 'pct': min(100, pct),
        })
    return conversao


def _calcular_funil(stages, ocorrencias):
    """Contagem e percentual por etapa do funil."""
    top = ocorrencias[stages[0]['key']] or 1
    return [
        {'key': s['key'], 'name': s['name'], 'color': s['color'],
         'count': ocorrencias[s['key']],
         'pct': round(ocorrencias[s['key']] / top * 100) if top else 0}
        for s in stages
    ]


def _buscar_atividade_recente(tid, negocios, stage_map):
    """Ultimas movimentacoes (ou fallback: ultimos negocios)."""
    movs = Movimentacao.objects.select_related('negocio__contato', 'autor')
    if tid is not None:
        movs = movs.filter(negocio__contato__tenant_id=tid)
    movs = list(movs.order_by('-created_at', '-id')[:8])
    if movs:
        return [
            {
                'id': m.negocio.contato.id, 'nome': m.negocio.contato.nome,
                'empresa': m.negocio.contato.empresa,
                'valor': _brl_curto(m.negocio.valor),
                'stage': stage_map.get(m.para_stage, {'name': m.para_stage, 'color': '#888'}),
                'de': stage_map.get(m.de_stage, {'name': m.de_stage, 'color': '#888'}) if m.de_stage else None,
                'autor': m.autor.nome if m.autor else '\u2014',
                'quando': m.created_at,
            }
            for m in movs
        ]
    return [
        {
            'id': n.contato.id, 'nome': n.contato.nome,
            'empresa': n.contato.empresa, 'valor': _brl_curto(n.valor),
            'stage': stage_map.get(n.stage, {'name': n.stage, 'color': '#888'}),
            'de': None, 'autor': None, 'quando': None,
        }
        for n in negocios.order_by('-updated_at')[:8]
    ]


def _analise_funil_valor(stages, negocios):
    """Valor total por etapa + ticket medio (query unica com annotate)."""
    agg = negocios.values('stage').annotate(total=Sum('valor')).order_by('stage')
    por_etapa_map = {r['stage']: float(r['total'] or 0) for r in agg}
    por_etapa = []
    for st in stages:
        total = por_etapa_map.get(st['key'], 0)
        por_etapa.append({
            'key': st['key'], 'name': st['name'], 'color': st['color'],
            'total': total, 'total_label': _brl_curto(total), 'pct': 0,
        })
    max_etapa = max([p['total'] for p in por_etapa] + [1])
    for p in por_etapa:
        p['pct'] = round(p['total'] / max_etapa * 100) if max_etapa else 0
    stats = negocios.exclude(stage__in=['perdido', 'fechado']).aggregate(
        qtd=Count('id'), valor_total=Sum('valor'),
    )
    qtd_ativos = stats['qtd'] or 0
    valor_funil_raw = float(stats['valor_total'] or 0)
    ticket_medio = _brl_curto(round(valor_funil_raw / qtd_ativos)) if qtd_ativos else 'R$ 0'
    return por_etapa, ticket_medio


def _buscar_metas_vendedor(tid, hoje):
    """Atingimento de metas por vendedor no mes."""
    if tid is None:
        return []
    primeiro_do_mes = hoje.replace(day=1)
    inicio_mes = timezone.make_aware(datetime.combine(primeiro_do_mes, time.min))
    metas_mes = dict(
        MetaVendedor.objects.filter(mes=primeiro_do_mes, usuario__tenant_id=tid)
        .values_list('usuario_id', 'valor')
    )
    vendedores = list(Usuario.objects.filter(tenant_id=tid).order_by('nome'))
    fechados = (
        Negocio.objects.filter(
            tenant_id=tid, stage='fechado', updated_at__gte=inicio_mes,
            responsavel_id__in=[u.id for u in vendedores],
        )
        .values('responsavel_id')
        .annotate(total=Sum('valor'), qtd=Count('id'))
    )
    vendido_por = {f['responsavel_id']: f for f in fechados}
    metas = []
    for u in vendedores:
        meta_valor = float(metas_mes.get(u.id) or 0)
        dados_venda = vendido_por.get(u.id) or {}
        vendido = float(dados_venda.get('total') or 0)
        qtd = dados_venda.get('qtd') or 0
        pct = round(vendido / meta_valor * 100) if meta_valor else None
        metas.append({
            'id': u.id, 'nome': u.nome, 'iniciais': _iniciais(u.nome),
            'meta': meta_valor, 'meta_label': _brl_curto(meta_valor) if meta_valor else '\u2014',
            'vendido': vendido, 'vendido_label': _brl_curto(vendido),
            'qtd_fechados': qtd,
            'pct': min(100, pct) if pct is not None else None,
            'atingiu': pct is not None and pct >= 100,
            'cor': '#7fe3c4' if pct is not None and pct >= 100 else ('#fbbf24' if pct is not None and pct >= 50 else '#fb7185'),
            'tem_meta': meta_valor > 0,
        })
    metas.sort(key=lambda m: (not m['tem_meta'], m['pct'] if m['pct'] is not None else -1), reverse=True)
    return metas


def _buscar_tarefas_alerta(tid, hoje):
    """Tarefas atrasadas + de hoje."""
    if tid is None:
        return []
    return [
        {
            'id': t.id, 'titulo': t.titulo,
            'contato_id': t.contato_id,
            'contato_nome': t.contato.nome if t.contato else '',
            'vencimento': t.vencimento, 'atrasada': t.vencimento < hoje,
        }
        for t in Tarefa.objects.filter(
            tenant_id=tid, concluida=False, vencimento__lte=hoje
        ).select_related('contato').order_by('vencimento')[:8]
    ]


def _agrupar_por_origem(negocios):
    """Negocios agrupados por origem (query unica com annotate)."""
    total = negocios.count()
    agg = negocios.values('contato__origem').annotate(
        count=Count('id'),
        fechados=Count('id', filter=Q(stage='fechado')),
    )
    por_origem = []
    for r in agg:
        origem = r['contato__origem'] or 'Sem origem'
        if origem in ORIGENS or r['contato__origem'] is None:
            por_origem.append({
                'nome': origem, 'count': r['count'],
                'pct': round(r['count'] / total * 100) if total else 0,
                'fechados': r['fechados'],
            })
    return por_origem


def _agrupar_por_segmento(negocios):
    """Negocios agrupados por segmento (valor total, query unica com annotate)."""
    agg = negocios.values('contato__seg').annotate(total=Sum('valor')).order_by('-total')
    por_segmento = []
    for r in agg:
        key = r['contato__seg']
        if key in SEGS:
            info = SEGS[key]
            total = float(r['total'] or 0)
            if total > 0:
                por_segmento.append({
                    'label': info['label'], 'color': info['color'],
                    'total': total, 'total_label': _brl_curto(total),
                })
    return por_segmento


def _buscar_melhores_negocios(negocios, stage_map):
    """Top 5 negocios em aberto por valor."""
    ativos = negocios.exclude(stage__in=['perdido', 'fechado'])
    melhores = [
        {
            'id': n.contato_id, 'nome': n.titulo or n.contato.nome,
            'empresa': n.contato.empresa, 'valor': float(n.valor),
            'valor_label': _brl(n.valor),
            'stage': stage_map.get(n.stage, {'name': n.stage, 'color': '#888'}),
        }
        for n in ativos.order_by('-valor')[:5]
    ]
    max_melhor = max([m['valor'] for m in melhores] + [1])
    for m in melhores:
        m['pct'] = round(m['valor'] / max_melhor * 100)
    return melhores


def _buscar_atividade_time(tid, inicio30):
    """Atividade do time: movimentacoes + notas por membro (ultimos 30 dias, query unica)."""
    movs_agg = Movimentacao.objects.filter(created_at__gte=inicio30)
    notas_agg = Nota.objects.filter(created_at__gte=inicio30)
    if tid is not None:
        movs_agg = movs_agg.filter(negocio__contato__tenant_id=tid)
        notas_agg = notas_agg.filter(contato__tenant_id=tid)
    movs_por = movs_agg.values('autor_id', 'autor__nome').annotate(cnt=Count('id'))
    notas_por = notas_agg.values('autor_id', 'autor__nome').annotate(cnt=Count('id'))
    atv = {}
    for r in movs_por:
        chave = r['autor_id'] or 0
        e = atv.setdefault(chave, {'nome': r['autor__nome'] or 'Sem autor', 'movs': 0, 'notas': 0})
        e['movs'] = r['cnt']
    for r in notas_por:
        chave = r['autor_id'] or 0
        e = atv.setdefault(chave, {'nome': r['autor__nome'] or 'Sem autor', 'movs': 0, 'notas': 0})
        e['notas'] = r['cnt']
    atividade = sorted(atv.values(), key=lambda e: e['movs'] + e['notas'], reverse=True)[:6]
    for e in atividade:
        e['iniciais'] = _iniciais(e['nome'])
        e['total'] = e['movs'] + e['notas']
    return atividade


def _calcular_velocidade(negocios, stage_map):
    """Tempo medio que negocios permanecem em cada etapa."""
    acum = {}
    for negocio in negocios.filter(movimentacoes__isnull=False).prefetch_related('movimentacoes'):
        movs_ord = sorted(negocio.movimentacoes.all(), key=lambda m: m.created_at)
        prev_ts = negocio.created_at
        for m in movs_ord:
            de = m.de_stage or 'interessado'
            dias = max(0.0, (m.created_at - prev_ts).total_seconds() / 86400)
            a = acum.setdefault(de, [0.0, 0])
            a[0] += dias
            a[1] += 1
            prev_ts = m.created_at
    max_vel = max([a[0] / a[1] for a in acum.values()] + [1])
    velocidade = []
    for key, (total, count) in acum.items():
        media = total / count
        info = stage_map.get(key, {'name': key, 'color': '#888'})
        velocidade.append({
            'name': info['name'], 'color': info['color'],
            'label': f'{media:.1f} d',
            'pct': round(media / max_vel * 100) if max_vel else 0,
        })
    velocidade.sort(key=lambda v: float(v['label'].replace(' d', '').replace(',', '.')), reverse=True)
    return velocidade


def _buscar_dados_baii(tenant_id=None):
    """Pirâmide de graus — membros ativos agrupados pelo maior grau registrado.

    A ordem das faixas é fixa: base 4–14, depois 15–18, 19–30, 31–32 e 33.
    Membros sem grau registrado não entram no total.
    """
    try:
        faixas = LocalRepository(tenant_id).membros_ativos_por_faixa_de_graus()
    except DBError as e:
        logger.error('Erro ao buscar membros por faixa de grau: %s', e)
        faixas = []

    itens = _para_svg_pyramide(faixas)
    return {
        'baii_ativos': itens, 'baii_ativos_svg': _pyramide_svg(itens),
        'baii_ativos_total': sum(i['count'] for i in itens),
    }


def _buscar_candidatos(tid):
    """Candidatos mais recentes do tenant — quem quer ingressar (recepção).

    Retorna todos para a paginação do card (5 por página no cliente):
    nome, loja que pretende ingressar, data de inclusão e loja simbólica.
    """
    from candidatos.models import Candidato

    if not tid:
        return {'itens': [], 'total': 0}
    qs = Candidato.objects.filter(tenant_id=tid).order_by('-data_inscricao')
    itens = [{
        'nome': c.nome_completo,
        'loja': c.loja,
        'data': timezone.localtime(c.data_inscricao).strftime('%d/%m/%y')
                if c.data_inscricao else '',
    } for c in qs]
    return {'itens': itens, 'total': len(itens)}


def _buscar_dados_gprb(ano_corrente, tenant_id=None):
    """Busca os dados de membros do dashboard no banco local, com fallback vazio."""
    repo = LocalRepository(tenant_id)

    def _safe(fn, *a, **kw):
        try:
            return fn(*a, **kw)
        except DBError as e:
            logger.error('Erro ao buscar %s: %s', fn.__name__, e)
            return [] if fn.__name__ != 'anuidade_card' else {}

    return {
        'chart_labels': _safe(repo.membros_por_mes, meses=36),
        'anuidade': _safe(repo.anuidade_card, ano=anuidade_ano_referencia()),
        'rito_dados': _safe(repo.membros_por_rito),
        'idade_dados': _safe(repo.membros_por_idade_faixa),
        'potencia_dados': _safe(repo.membros_por_potencia),
        'tempo_maconaria_dados': _safe(repo.membros_por_tempo_maconaria),
        'ranking_lojas_dados': _safe(repo.ranking_lojas),
        'agendamento_dados': _safe(repo.agendamento_lojas),
    }


@web_login_required
def index(request):
    tid = request.session.get('usuario', {}).get('tenant_id')
    nicho = nicho_da_sessao(request)
    stages = etapas_do_tenant(tid, nicho)
    stage_map = etapa_map_do_tenant(tid, nicho)
    negocios = filtro_tenant(request, Negocio.objects.select_related('contato'))

    dashboard_cache = DashboardCache(DjangoCacheBackend())

    cached = dashboard_cache.get_kpis(tid, nicho)

    hoje = date.today()
    inicio30 = timezone.make_aware(datetime.combine(hoje - timedelta(days=30), time.min))
    ano_corrente = hoje.year

    if cached is None:
        resumo = _resumo(request, negocios)
        ocorrencias_agg = negocios.values('stage').annotate(cnt=Count('id'))
        ocorrencias = {s['key']: 0 for s in stages}
        for r in ocorrencias_agg:
            ocorrencias[r['stage']] = r['cnt']
        timeline, timeline_max = _calcular_timeline(negocios, hoje)
        conversao = _calcular_conversao(stages, ocorrencias)
        funil = _calcular_funil(stages, ocorrencias)
        por_etapa, ticket_medio = _analise_funil_valor(stages, negocios)
        por_origem = _agrupar_por_origem(negocios)
        por_segmento = _agrupar_por_segmento(negocios)
        melhores = _buscar_melhores_negocios(negocios, stage_map)
        velocidade = _calcular_velocidade(negocios, stage_map)
        cached = {
            'resumo': resumo, 'timeline': timeline, 'timeline_max': timeline_max,
            'conversao': conversao, 'funil': funil, 'por_etapa': por_etapa,
            'ticket_medio': ticket_medio, 'por_origem': por_origem,
            'por_segmento': por_segmento, 'melhores': melhores,
            'velocidade': velocidade,
        }
        dashboard_cache.set_kpis(tid, nicho, cached)
    else:
        resumo = cached['resumo']
        timeline = cached['timeline']
        timeline_max = cached['timeline_max']
        conversao = cached['conversao']
        funil = cached['funil']
        por_etapa = cached['por_etapa']
        ticket_medio = cached['ticket_medio']
        por_origem = cached['por_origem']
        por_segmento = cached['por_segmento']
        melhores = cached['melhores']
        velocidade = cached['velocidade']

    recentes = _buscar_atividade_recente(tid, negocios, stage_map)
    metas_dashboard = _buscar_metas_vendedor(tid, hoje)
    tarefas_alerta = _buscar_tarefas_alerta(tid, hoje)
    atividade = _buscar_atividade_time(tid, inicio30)
    baii = _buscar_dados_baii(tid)
    dados_gprb = _buscar_dados_gprb(ano_corrente, tid)
    chart_data = dados_gprb.get('chart_labels', ([], []))
    if isinstance(chart_data, tuple) and len(chart_data) == 2:
        chart_labels, chart_valores = chart_data
    else:
        chart_labels, chart_valores = [], []

    return render(request, 'dashboard/index.html', {
        'kpis': resumo,
        'chart_membros_labels': chart_labels,
        'chart_membros_valores': chart_valores,
        'anualidade': dados_gprb['anuidade'],
        'timeline': timeline, 'timeline_max': timeline_max,
        'timeline_svg': _timeline_svg(timeline),
        'conversao': conversao, 'funil': funil,
        'funil_svg': _funnel_svg(funil),
        'recentes': recentes, 'por_etapa': por_etapa,
        'tarefas_alerta': tarefas_alerta, 'ticket_medio': ticket_medio,
        'por_origem': por_origem, 'por_segmento': por_segmento,
        'melhores': melhores, 'atividade': atividade,
        'velocidade': velocidade, 'metas_dashboard': metas_dashboard,
        'atualizado_em': timezone.localtime().strftime('%H:%M:%S'),
        'baii_ativos': baii['baii_ativos'],
        'baii_ativos_svg': baii['baii_ativos_svg'],
        'baii_ativos_total': baii['baii_ativos_total'],
        'ano_corrente': ano_corrente,
        'ano_anuidade': anuidade_ano_referencia(),
        'rito_dados': dados_gprb['rito_dados'],
        'idade_dados': dados_gprb['idade_dados'],
        'potencia_dados': dados_gprb['potencia_dados'],
        'tempo_maconaria_dados': dados_gprb['tempo_maconaria_dados'],
        'ranking_lojas_dados': dados_gprb['ranking_lojas_dados'],
        'candidatos_card': _buscar_candidatos(tid),
        'agendamento_dados': dados_gprb['agendamento_dados'],
    })
