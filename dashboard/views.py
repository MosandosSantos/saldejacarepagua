"""Views web do Dashboard — KPIs, timeline, conversao, funil, recentes e analises avancadas."""

import html
import logging
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

logger = logging.getLogger(__name__)

from acesso.decorators import filtro_tenant, nicho_da_sessao, web_login_required
from acesso.models import MetaVendedor, Tenant, Usuario
from contatos.models import Movimentacao, Negocio, Nota
from core.dominio import ORIGENS, PESOS_ETAPA, SEGS
from core.gprb import membros_por_classe, total_membros, novos_membros_ano, total_lojas_ativas, total_lojas_cadastradas, membros_por_mes, anualidade_resumo, anuidade_ano_referencia, membros_por_rito, membros_por_idade_faixa, membros_por_potencia, membros_por_tempo_maconaria, ranking_lojas, ranking_lojas_mx, proximas_sessoes, agendamento_lojas
from core.utils import brl as _brl, brl_curto as _brl_curto, iniciais as _iniciais
from funil.models import etapa_map_do_tenant, etapas_do_tenant
from tarefas.models import Tarefa

# Gestao (GEOD-CEOD)
from gestao.models import Congressista, Inscricao, Pagamento


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


def _funnel_svg(funil):
    """Gráfico de funil 3D em SVG — tons de verde para o funil de BAII."""
    steps = list(funil)
    if not steps:
        return ''
    top = steps[0]['count'] or 1
    W, sliceH, gap, depthX, depthY, topY = 340, 62, 5, 22, 14, 16
    cx, n = W / 2, len(steps)
    shadowY = topY + n * (sliceH + gap) + depthY + 10
    max_half = cx * 0.92

    defs = '<defs>'
    for i, s in enumerate(steps):
        dark = _shade(s['color'], -0.42)
        defs += (f'<linearGradient id="f3g{i}" x1="0" y1="0" x2="0" y2="1">'
                 f'<stop offset="0%" stop-color="{_esc_attr(s['color'])}" stop-opacity="0.98"/>'
                 f'<stop offset="100%" stop-color="{_esc_attr(dark)}" stop-opacity="0.9"/></linearGradient>')
        defs += (f'<linearGradient id="f3s{i}" x1="0" y1="0" x2="1" y2="0">'
                 f'<stop offset="0%" stop-color="{_esc_attr(dark)}" stop-opacity="0.78"/>'
                 f'<stop offset="100%" stop-color="{_esc_attr(dark)}" stop-opacity="0.32"/></linearGradient>')
    defs += '</defs>'

    c = defs
    c += (f'<ellipse cx="{(cx + depthX * 0.4):.1f}" cy="{shadowY:.1f}" '
          f'rx="{(cx * 0.5):.1f}" ry="{(depthY * 0.9):.1f}" fill="rgba(0,0,0,0.4)"/>')

    for i, s in enumerate(steps):
        frac_top = 1 - (i / n) * 0.82
        frac_bot = 1 - ((i + 1) / n) * 0.82
        w_top, w_bot = frac_top * max_half, frac_bot * max_half
        y1 = topY + i * (sliceH + gap)
        y2 = y1 + sliceH
        fl, fr = cx - w_top, cx + w_top
        nl, nr = cx - w_bot, cx + w_bot

        c += (f'<polygon points="{fl:.1f},{y1:.1f} {fr:.1f},{y1:.1f} {nr:.1f},{y2:.1f} {nl:.1f},{y2:.1f}" '
              f'fill="url(#f3g{i})"/>')
        c += (f'<polygon points="{fr:.1f},{y1:.1f} {fr + depthX:.1f},{y1 - depthY:.1f} '
              f'{nr + depthX:.1f},{y2 - depthY:.1f} {nl:.1f},{y2:.1f}" fill="url(#f3s{i})"/>')
        c += (f'<line x1="{fl:.1f}" y1="{y1:.1f}" x2="{fr:.1f}" y2="{y1:.1f}" '
              f'stroke="rgba(255,255,255,0.24)" stroke-width="1.2"/>')
        c += (f'<text x="{cx:.1f}" y="{(y1 + sliceH / 2 + 4):.1f}" text-anchor="middle" font-size="14" '
              f'font-weight="700" font-family="JetBrains Mono, monospace" fill="#fff" opacity="0.92">{s["count"]}</text>')
        if i == 0:
            ecx = (fl + fr + depthX) / 2
            erx = (fr + depthX - fl) / 2
            c += (f'<ellipse cx="{ecx:.1f}" cy="{y1:.1f}" rx="{erx:.1f}" ry="{depthY * 0.75:.1f}" '
                  f'fill="{_esc_attr(s['color'])}" opacity="0.95"/>')
            c += (f'<ellipse cx="{ecx:.1f}" cy="{y1:.1f}" rx="{erx:.1f}" ry="{depthY * 0.75:.1f}" '
                  f'fill="none" stroke="#74b3c6" stroke-width="1.4" opacity="0.6"/>')

    return f'<svg viewBox="0 0 {W} {shadowY + 8}" class="w-full">' + c + '</svg>'


def _baii_svg(baii):
    """Gráfico de funil 3D em tons de verde para o funil de BAII (Bem Amados Irmãos)."""
    steps = list(baii)
    if not steps:
        return ''
    top = steps[0]['count'] or 1
    W, sliceH, gap, depthX, depthY, topY = 340, 62, 5, 22, 14, 16
    cx, n = W / 2, len(steps)
    shadowY = topY + n * (sliceH + gap) + depthY + 10
    max_half = cx * 0.92

    # Tons de azul: escuro (base) → médio → claro (topo) — tema GEOD-CEOD
    azul_escuro = '#1a5fb4'    # MESA (base)
    azul_medio = '#3b7ded'     # EN (meio)
    azul_claro = '#93b8f7'     # CBCS (topo)
    verdes = [azul_escuro, azul_medio, azul_claro]

    defs = '<defs>'
    for i, s in enumerate(steps):
        cor = verdes[i] if i < len(verdes) else s.get('color', '#1a5fb4')
        dark = _shade(cor, -0.42)
        defs += (f'<linearGradient id="baii{i}" x1="0" y1="0" x2="0" y2="1">'
                 f'<stop offset="0%" stop-color="{_esc_attr(cor)}" stop-opacity="0.98"/>'
                 f'<stop offset="100%" stop-color="{_esc_attr(dark)}" stop-opacity="0.9"/></linearGradient>')
        defs += (f'<linearGradient id="baiis{i}" x1="0" y1="0" x2="1" y2="0">'
                 f'<stop offset="0%" stop-color="{_esc_attr(dark)}" stop-opacity="0.78"/>'
                 f'<stop offset="100%" stop-color="{_esc_attr(dark)}" stop-opacity="0.32"/></linearGradient>')
    defs += '</defs>'

    c = defs
    c += (f'<ellipse cx="{(cx + depthX * 0.4):.1f}" cy="{shadowY:.1f}" '
          f'rx="{(cx * 0.5):.1f}" ry="{(depthY * 0.9):.1f}" fill="rgba(0,0,0,0.4)"/>')

    for i, s in enumerate(steps):
        cor = verdes[i] if i < len(verdes) else s.get('color', '#1a5fb4')
        frac_top = 1 - (i / n) * 0.82
        frac_bot = 1 - ((i + 1) / n) * 0.82
        w_top, w_bot = frac_top * max_half, frac_bot * max_half
        y1 = topY + i * (sliceH + gap)
        y2 = y1 + sliceH
        fl, fr = cx - w_top, cx + w_top
        nl, nr = cx - w_bot, cx + w_bot

        c += (f'<polygon points="{fl:.1f},{y1:.1f} {fr:.1f},{y1:.1f} {nr:.1f},{y2:.1f} {nl:.1f},{y2:.1f}" '
              f'fill="url(#baii{i})"/>')
        c += (f'<polygon points="{fr:.1f},{y1:.1f} {fr + depthX:.1f},{y1 - depthY:.1f} '
              f'{nr + depthX:.1f},{y2 - depthY:.1f} {nl:.1f},{y2:.1f}" fill="url(#baiis{i})"/>')
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

    # ---- KPIs do saldorer (banco GPRB) ----
    ano_corrente = hoje.year
    lojas_ativas = total_lojas_ativas()
    lojas_total = total_lojas_cadastradas()
    membros_ativos = total_membros(apenas_ativos=True)
    membros_total = total_membros(apenas_ativos=False)
    novos_membros = novos_membros_ano(ano=ano_corrente)
    sessoes_ano = Inscricao.objects.filter(
        criado_em__year=ano_corrente,
    ).count()
    caixa_raw = (
        Pagamento.objects.filter(status__in=['confirmado', 'sistema'])
        .aggregate(total=Sum('valor'))['total'] or 0
    )

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
        # Saldorer (GPRB)
        'lojas_ativas': lojas_ativas,
        'lojas_total': lojas_total,
        'membros_ativos': membros_ativos,
        'membros_total': membros_total,
        'novos_membros': novos_membros,
        'sessoes_ano': sessoes_ano,
        'caixa': _brl(caixa_raw),
        'caixa_raw': float(caixa_raw),
    }


@web_login_required
def dados(request):
    """Auto-refresh leve: números do cabeçalho em JSON para o polling do dashboard."""
    resumo = _resumo(request)
    resumo['atualizado_em'] = timezone.localtime().strftime('%H:%M:%S')
    return JsonResponse(resumo)


@web_login_required
def index(request):
    tid = request.session.get('usuario', {}).get('tenant_id')
    nicho = nicho_da_sessao(request)
    stages = etapas_do_tenant(tid, nicho)
    stage_map = etapa_map_do_tenant(tid, nicho)
    negocios = filtro_tenant(request, Negocio.objects.select_related('contato'))
    resumo = _resumo(request, negocios)

    hoje = date.today()
    inicio30 = timezone.make_aware(datetime.combine(hoje - timedelta(days=30), time.min))

    # Timeline: últimos 30 dias por created_at dos negócios (novos negócios/dia)
    por_dia = defaultdict(int)
    for uc in negocios.values_list('created_at', flat=True):
        if uc is not None:
            por_dia[uc.date()] += 1
    timeline = []
    d = hoje - timedelta(days=29)
    while d <= hoje:
        timeline.append({'data': f'{d.day:02d}/{d.month:02d}', 'valor': por_dia.get(d, 0)})
        d += timedelta(days=1)
    timeline_max = max([p['valor'] for p in timeline] + [1])

    # Conversão por etapa (pares consecutivos, ignorando perdido)
    st_validos = [s for s in stages if s['key'] != 'perdido']
    ocorrencias = {s['key']: negocios.filter(stage=s['key']).count() for s in stages}
    conversao = []
    for i in range(1, len(st_validos)):
        prev, cur = st_validos[i - 1], st_validos[i]
        pct = round(cur and (ocorrencias[cur['key']] / ocorrencias[prev['key']] * 100)) if ocorrencias[prev['key']] else 0
        conversao.append({
            'de': prev['name'], 'para': cur['name'],
            'cor': cur['color'],
            'pct': min(100, pct),
        })

    top = ocorrencias[st_validos[0]['key']] or negocios.count() or 1
    funil = [
        {'key': s['key'], 'name': s['name'], 'color': s['color'],
         'count': ocorrencias[s['key']],
         'pct': round(ocorrencias[s['key']] / top * 100) if top else 0}
        for s in stages
    ]

    # Atividade recente: movimentações (com contexto) ou últimos negócios (fallback)
    movs = Movimentacao.objects.select_related('negocio__contato', 'autor')
    if tid is not None:
        movs = movs.filter(negocio__contato__tenant_id=tid)
    movs = list(movs.order_by('-created_at', '-id')[:8])
    if movs:
        recentes = [
            {
                'id': m.negocio.contato.id,
                'nome': m.negocio.contato.nome,
                'empresa': m.negocio.contato.empresa,
                'valor': _brl_curto(m.negocio.valor),
                'stage': stage_map.get(m.para_stage, {'name': m.para_stage, 'color': '#888'}),
                'de': stage_map.get(m.de_stage, {'name': m.de_stage, 'color': '#888'}) if m.de_stage else None,
                'autor': m.autor.nome if m.autor else '—',
                'quando': m.created_at,
            }
            for m in movs
        ]
    else:
        recentes = [
            {
                'id': n.contato.id,
                'nome': n.contato.nome,
                'empresa': n.contato.empresa,
                'valor': _brl_curto(n.valor),
                'stage': stage_map.get(n.stage, {'name': n.stage, 'color': '#888'}),
                'de': None,
                'autor': None,
                'quando': None,
            }
            for n in negocios.order_by('-updated_at')[:8]
        ]

    # --- Análise do funil ---
    por_etapa = []
    for st in stages:
        total = negocios.filter(stage=st['key']).aggregate(s=Sum('valor'))['s'] or 0
        por_etapa.append({
            'key': st['key'], 'name': st['name'], 'color': st['color'],
            'total': total, 'total_label': _brl_curto(total), 'pct': 0,
        })
    max_etapa = max([p['total'] for p in por_etapa] + [1])
    for p in por_etapa:
        p['pct'] = round(p['total'] / max_etapa * 100) if max_etapa else 0

    qtd_ativos = resumo['ativos']
    valor_funil_raw = sum(float(n.valor) for n in negocios.exclude(stage__in=['perdido', 'fechado']))
    ticket_medio = _brl_curto(round(valor_funil_raw / qtd_ativos)) if qtd_ativos else 'R$ 0'

    # Metas por vendedor (atingimento no mês atual)
    metas_dashboard = []
    if tid is not None:
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
        for u in vendedores:
            meta_valor = float(metas_mes.get(u.id) or 0)
            dados_venda = vendido_por.get(u.id) or {}
            vendido = float(dados_venda.get('total') or 0)
            qtd = dados_venda.get('qtd') or 0
            pct = round(vendido / meta_valor * 100) if meta_valor else None
            metas_dashboard.append({
                'id': u.id,
                'nome': u.nome,
                'iniciais': _iniciais(u.nome),
                'meta': meta_valor,
                'meta_label': _brl_curto(meta_valor) if meta_valor else '—',
                'vendido': vendido,
                'vendido_label': _brl_curto(vendido),
                'qtd_fechados': qtd,
                'pct': min(100, pct) if pct is not None else None,
                'atingiu': pct is not None and pct >= 100,
                'cor': '#7fe3c4' if pct is not None and pct >= 100 else ('#fbbf24' if pct is not None and pct >= 50 else '#fb7185'),
                'tem_meta': meta_valor > 0,
            })
        metas_dashboard.sort(key=lambda m: (not m['tem_meta'], m['pct'] if m['pct'] is not None else -1), reverse=True)

    # Tarefas & lembretes: atrasadas + de hoje (alerta no topo do dashboard)
    tarefas_alerta = []
    if tid is not None:
        tarefas_alerta = [
            {
                'id': t.id,
                'titulo': t.titulo,
                'contato_id': t.contato_id,
                'contato_nome': t.contato.nome if t.contato else '',
                'vencimento': t.vencimento,
                'atrasada': t.vencimento < hoje,
            }
            for t in Tarefa.objects.filter(
                tenant_id=tid, concluida=False, vencimento__lte=hoje
            ).select_related('contato').order_by('vencimento')[:8]
        ]

    total_negocios = negocios.count()
    por_origem = []
    for origem in ORIGENS:
        qs = negocios.filter(contato__origem=origem)
        n = qs.count()
        por_origem.append({
            'nome': origem, 'count': n,
            'pct': round(n / total_negocios * 100) if total_negocios else 0,
            'fechados': qs.filter(stage='fechado').count(),
        })
    sem_origem = negocios.exclude(contato__origem__in=ORIGENS).count()
    if sem_origem:
        por_origem.append({
            'nome': 'Sem origem', 'count': sem_origem,
            'pct': round(sem_origem / total_negocios * 100) if total_negocios else 0,
            'fechados': 0,
        })

    por_segmento = []
    for key, info in SEGS.items():
        qs = negocios.filter(contato__seg=key)
        total = qs.aggregate(s=Sum('valor'))['s'] or 0
        if qs.count():
            por_segmento.append({
                'label': info['label'], 'color': info['color'],
                'total': total, 'total_label': _brl_curto(total),
            })
    por_segmento.sort(key=lambda s: s['total'], reverse=True)

    # --- Novidades da Fase C ---

    # Melhores negócios (em aberto, top 5 por valor)
    ativos_qs = negocios.exclude(stage__in=['perdido', 'fechado'])
    melhores = [
        {
            'id': n.contato_id,
            'nome': n.titulo or n.contato.nome,
            'empresa': n.contato.empresa,
            'valor': float(n.valor),
            'valor_label': _brl(n.valor),
            'stage': stage_map.get(n.stage, {'name': n.stage, 'color': '#888'}),
        }
        for n in ativos_qs.order_by('-valor')[:5]
    ]
    max_melhor = max([m['valor'] for m in melhores] + [1])
    for m in melhores:
        m['pct'] = round(m['valor'] / max_melhor * 100)

    # Atividade do time: movimentações + notas por membro (últimos 30 dias)
    movs_atv = Movimentacao.objects.filter(created_at__gte=inicio30).select_related('autor')
    notas_atv = Nota.objects.filter(created_at__gte=inicio30).select_related('autor')
    if tid is not None:
        movs_atv = movs_atv.filter(negocio__contato__tenant_id=tid)
        notas_atv = notas_atv.filter(contato__tenant_id=tid)
    atv = {}
    for m in movs_atv:
        chave = m.autor_id or 0
        e = atv.setdefault(chave, {'nome': m.autor.nome if m.autor else 'Sem autor', 'movs': 0, 'notas': 0})
        e['movs'] += 1
    for n in notas_atv:
        chave = n.autor_id or 0
        e = atv.setdefault(chave, {'nome': n.autor.nome if n.autor else 'Sem autor', 'movs': 0, 'notas': 0})
        e['notas'] += 1
    atividade = sorted(atv.values(), key=lambda e: e['movs'] + e['notas'], reverse=True)[:6]
    for e in atividade:
        e['iniciais'] = _iniciais(e['nome'])
        e['total'] = e['movs'] + e['notas']

    # Velocidade média por etapa (tempo que os negócios passam em cada etapa)
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
            'name': info['name'],
            'color': info['color'],
            'label': f'{media:.1f} d',
            'pct': round(media / max_vel * 100) if max_vel else 0,
        })
    velocidade.sort(key=lambda v: float(v['label'].replace(' d', '').replace(',', '.')), reverse=True)

    # --- Dados do Funil de BAII (Bem Amados Irmãos) ---
    # Cores de azul para os 3 níveis (tema GEOD-CEOD)
    azul_mesa = '#1a5fb4'   # Mestre de Santo André (base)
    azul_en = '#3b7ded'     # Escudeiro Noviço (meio)
    azul_cbcs = '#93b8f7'   # Cavaleiro Benfeitor (topo)
    cores_baii = [azul_mesa, azul_en, azul_cbcs]

    # BAII ATIVOS: todos os membros ativos por classe
    try:
        baii_ativos_raw = membros_por_classe(apenas_ativos=True)
    except Exception as e:
        logger.error('Erro ao buscar membros por classe (ativos): %s', e)
        baii_ativos_raw = []

    # Ordem: MESA (base), EN (meio), CBCS (topo)
    ordem_classes = {'Mestre de Santo Andr': 0, 'Escudeiro': 1, 'Cavaleiro': 2}
    baii_ativos_raw.sort(key=lambda x: next(
        (v for k, v in ordem_classes.items() if k in x['name']), 99
    ))
    total_ativos = sum(m['total'] for m in baii_ativos_raw) or 1
    baii_ativos = [
        {'key': m['abbr'], 'name': m['abbr'], 'count': m['total'],
         'color': cores_baii[i] if i < len(cores_baii) else '#166534',
         'pct': round(m['total'] / total_ativos * 100)}
        for i, m in enumerate(baii_ativos_raw)
    ]
    baii_ativos_svg = _baii_svg(baii_ativos)

    # BAII CADASTRADOS: membros cadastrados no ano corrente
    ano_corrente = date.today().year
    try:
        baii_ano_raw = membros_por_classe(apenas_ativos=False, ano=ano_corrente)
    except Exception as e:
        logger.error('Erro ao buscar membros por classe (ano): %s', e)
        baii_ano_raw = []

    baii_ano_raw.sort(key=lambda x: next(
        (v for k, v in ordem_classes.items() if k in x['name']), 99
    ))
    total_ano = sum(m['total'] for m in baii_ano_raw) or 1
    baii_ano = [
        {'key': m['abbr'], 'name': m['abbr'], 'count': m['total'],
         'color': cores_baii[i] if i < len(cores_baii) else '#166534',
         'pct': round(m['total'] / total_ano * 100)}
        for i, m in enumerate(baii_ano_raw)
    ]
    baii_ano_svg = _baii_svg(baii_ano)

    # Grafico de linha: admisses por mes (ultimos 36 meses)
    chart_labels, chart_valores = membros_por_mes(meses=36)

    # Anualidade
    ano_anuidade = anuidade_ano_referencia()
    anualidade = anualidade_resumo(ano=ano_anuidade)

    # Rito no simbolismo
    try:
        rito_dados = membros_por_rito()
    except Exception as e:
        logger.error('Erro ao buscar membros por rito: %s', e)
        rito_dados = []

    # Idade por faixa
    try:
        idade_dados = membros_por_idade_faixa()
    except Exception as e:
        logger.error('Erro ao buscar membros por faixa etaria: %s', e)
        idade_dados = []

    # Potencia do simbolismo
    try:
        potencia_dados = membros_por_potencia()
    except Exception as e:
        logger.error('Erro ao buscar membros por potencia: %s', e)
        potencia_dados = []

    # Tempo na maconaria
    try:
        tempo_maconaria_dados = membros_por_tempo_maconaria()
    except Exception as e:
        logger.error('Erro ao buscar membros por tempo de macomaria: %s', e)
        tempo_maconaria_dados = []

    # Ranking lojas (top 10)
    try:
        ranking_lojas_dados = ranking_lojas()
    except Exception as e:
        logger.error('Erro ao buscar ranking de lojas: %s', e)
        ranking_lojas_dados = []

    # Ranking lojas MX (top 10 — últimos 3 anos)
    try:
        ranking_mx_dados = ranking_lojas_mx(anos=3)
    except Exception as e:
        logger.error('Erro ao buscar ranking MX: %s', e)
        ranking_mx_dados = []

    # Proximas sessoes (agenda das lojas)
    try:
        proximas_sessoes_dados = proximas_sessoes()
    except Exception as e:
        logger.error('Erro ao buscar proximas sessoes: %s', e)
        proximas_sessoes_dados = []

    # Agendamento de sessoes
    try:
        agendamento_dados = agendamento_lojas()
    except Exception as e:
        logger.error('Erro ao buscar agendamento de lojas: %s', e)
        agendamento_dados = []

    return render(request, 'dashboard/index.html', {
        'kpis': resumo,
        'chart_membros_labels': chart_labels,
        'chart_membros_valores': chart_valores,
        'anualidade': anualidade,
        'timeline': timeline,
        'timeline_max': timeline_max,
        'timeline_svg': _timeline_svg(timeline),
        'conversao': conversao,
        'funil': funil,
        'funil_svg': _funnel_svg(funil),
        'recentes': recentes,
        'por_etapa': por_etapa,
        'tarefas_alerta': tarefas_alerta,
        'ticket_medio': ticket_medio,
        'por_origem': por_origem,
        'por_segmento': por_segmento,
        'melhores': melhores,
        'atividade': atividade,
        'velocidade': velocidade,
        'metas_dashboard': metas_dashboard,
        'atualizado_em': timezone.localtime().strftime('%H:%M:%S'),
        'baii_ativos': baii_ativos,
        'baii_ativos_svg': baii_ativos_svg,
        'baii_ativos_total': sum(m['total'] for m in baii_ativos_raw),
        'baii_ano': baii_ano,
        'baii_ano_svg': baii_ano_svg,
        'baii_ano_total': sum(m['total'] for m in baii_ano_raw),
        'baii_ano_ano': ano_corrente,
        'ano_corrente': ano_corrente,
        'ano_anuidade': ano_anuidade,
        'rito_dados': rito_dados,
        'idade_dados': idade_dados,
        'potencia_dados': potencia_dados,
        'tempo_maconaria_dados': tempo_maconaria_dados,
        'ranking_lojas_dados': ranking_lojas_dados,
        'ranking_mx_dados': ranking_mx_dados,
        'proximas_sessoes_dados': proximas_sessoes_dados,
        'agendamento_dados': agendamento_dados,
    })
