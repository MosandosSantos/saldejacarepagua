"""Views do app 'relatorios' — dashboard gerencial de cobrança (PRD S7).

KPIs operacionais (base, CPC, retornos e produtividade por operador) com filtro
de período (hoje / 7 dias / 30 dias / mês), filtro por operador, gráficos SVG
da série diária e exportação em CSV e PDF. Tudo escopado por tenant.
"""

import csv
from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from acesso.decorators import tenant_id_da_sessao, web_login_required
from acesso.models import ROLE_ADMIN_COMPANY, ROLE_OPERACIONAL, Tenant, Usuario
from contatos.models import Contato
from discador.models import Chamada
from core.utils import brl_curto as _brl_curto, iniciais as _iniciais


def _periodo_por_chave(chave, hoje):
    """Período do relatório: (inicio, fim, label, chave) conforme `chave`.

    Filtros do PRD S7 (7.2): dia atual · últimos 7 dias · últimos 30 dias ·
    mês corrente. Padrão: últimos 30 dias.
    """
    fim = timezone.make_aware(datetime.combine(hoje, time.max))
    if chave == 'hoje':
        inicio = timezone.make_aware(datetime.combine(hoje, time.min))
        label = 'Hoje'
    elif chave == '7':
        inicio = timezone.make_aware(datetime.combine(hoje - timedelta(days=6), time.min))
        label = 'Últimos 7 dias'
    elif chave == 'mes':
        inicio = timezone.make_aware(datetime.combine(hoje.replace(day=1), time.min))
        label = 'Mês corrente'
    else:
        chave = '30'
        inicio = timezone.make_aware(datetime.combine(hoje - timedelta(days=29), time.min))
        label = 'Últimos 30 dias'
    return inicio, fim, label, chave


def _periodo(request):
    chave = request.GET.get('periodo', '30')
    return _periodo_por_chave(chave, timezone.localdate())


def _chamadas_scope(tid):
    qs = Chamada.objects.all()
    if tid is not None:
        qs = qs.filter(tenant_id=tid)
    return qs


def _contatos_scope(tid):
    qs = Contato.objects.all()
    if tid is not None:
        qs = qs.filter(tenant_id=tid)
    return qs


def _operador_do_filtro(request, tid):
    """Operador selecionado em `?operador=` — validado contra o tenant da sessão."""
    op_id = request.GET.get('operador')
    if not op_id or not op_id.isdigit():
        return None
    qs = Usuario.objects.filter(pk=int(op_id))
    if tid is not None:
        qs = qs.filter(tenant_id=tid)
    return qs.first()


def _kpis(tid, inicio, fim, operador_id=None):
    """Indicadores do relatório no período (7.1.1 a 7.1.5).

    `operador_id` (opcional) restringe CPC/retornos ao operador;
    a base em cobrança continua sendo da empresa inteira.
    """
    chamadas = _chamadas_scope(tid).filter(created_at__range=(inicio, fim))
    cpc_qs = _chamadas_scope(tid).filter(status='realizada', updated_at__range=(inicio, fim))
    retornos_qs = _chamadas_scope(tid).filter(
        status='retornar', retorno_em__isnull=False, retorno_em__range=(inicio, fim),
    )
    if operador_id is not None:
        chamadas = chamadas.filter(operador_id=operador_id)
        cpc_qs = cpc_qs.filter(operador_id=operador_id)
        retornos_qs = retornos_qs.filter(operador_id=operador_id)

    cpc = cpc_qs.count()
    retornos = retornos_qs.count()
    base_qs = _contatos_scope(tid).filter(tel_normalizado__gt='')
    base_total = base_qs.count()
    base_novos = base_qs.filter(created_at__range=(inicio, fim)).count()
    return {
        'base': base_total,
        'base_label': _brl_curto(base_total),
        'base_novos': base_novos,
        'cpc': cpc,
        'cpc_label': str(cpc),
        'retornos': retornos,
        'retornos_label': str(retornos),
        'chamadas': chamadas.count(),
        'chamadas_label': str(chamadas.count()),
    }


def _produtividade(tid, inicio, fim, operador_id=None):
    """Produtividade individual dos operadores no período (7.1.6)."""
    chamadas = _chamadas_scope(tid).filter(created_at__range=(inicio, fim))
    if operador_id is not None:
        chamadas = chamadas.filter(operador_id=operador_id)
    linhas = list(
        chamadas.filter(operador_id__isnull=False)
        .values('operador_id', 'operador__nome')
        .annotate(
            total=Count('id'),
            realizadas=Count('id', filter=Q(status='realizada')),
            retornos=Count('id', filter=Q(status='retornar')),
        )
        .order_by('-total')
    )
    itens = []
    for linha in linhas:
        op_id = linha['operador_id']
        itens.append({
            'id': op_id,
            'nome': linha['operador__nome'] or 'Operador',
            'iniciais': _iniciais(linha['operador__nome']),
            'chamadas': linha['total'],
            'realizadas': linha['realizadas'],
            'retornos': linha['retornos'],
        })
    return itens


def _serie_diaria(tid, inicio, fim, operador_id=None):
    """Série diária do período (no mínimo 7 dias): CPC.

    Agregação feita no banco (TruncDate + Count) — sem trazer todos os
    registros para o Python. As chaves de dia respeitam o timezone local
    (usa `localtime().date()` ao agrupar).
    """
    hoje = timezone.localdate()
    primeiro = inicio.date()
    if (hoje - primeiro).days < 7:
        primeiro = hoje - timedelta(days=6)
    dias = [primeiro + timedelta(days=i) for i in range((hoje - primeiro).days + 1)]

    cpc_qs = _chamadas_scope(tid).filter(status='realizada', updated_at__range=(inicio, fim))
    if operador_id is not None:
        cpc_qs = cpc_qs.filter(operador_id=operador_id)

    def _por_dia(qs, campo, agregacao):
        return {
            r['dia']: r['total']
            for r in qs.annotate(dia=TruncDate(campo)).values('dia').annotate(total=agregacao)
            if r['dia'] is not None
        }

    cpc_dia = _por_dia(cpc_qs, 'updated_at', Count('id'))

    serie = []
    for d in dias:
        serie.append({
            'data': f'{d.day:02d}/{d.month:02d}',
            'cpc': cpc_dia.get(d, 0),
        })
    return serie


def _linhas_svg(serie, campos):
    """Gráfico de linha SVG multi-série (mesmo visual do dashboard).

    `campos` = [(chave, cor, rotulo)]; cada série vira uma linha com área
    suave, pontos com tooltip e legenda acima do gráfico.
    """
    if not serie:
        return ''
    mx = max(max(d[c[0]] for c in campos) for d in serie) or 1
    W, H, pad_x, pad_t, pad_b = 660, 210, 30, 26, 30
    n = len(serie)

    def _xy(i, v):
        x = pad_x + (i / (n - 1)) * (W - pad_x * 2)
        y = (H - pad_b) - (v / mx) * (H - pad_t - pad_b)
        return x, y

    defs = '<defs>'
    for ci, (_chave, cor, _rotulo) in enumerate(campos):
        defs += (f'<linearGradient id="rlArea{ci}" x1="0" y1="0" x2="0" y2="1">'
                 f'<stop offset="0%" stop-color="{cor}" stop-opacity="0.22"/>'
                 f'<stop offset="100%" stop-color="{cor}" stop-opacity="0"/></linearGradient>')
        defs += (f'<filter id="rlGlow{ci}" x="-50%" y="-50%" width="200%" height="200%">'
                 f'<feGaussianBlur stdDeviation="2" result="b"/>'
                 f'<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
    defs += '</defs>'

    camadas = ''
    for ci, (chave, cor, _rotulo) in enumerate(campos):
        pts = [_xy(i, d[chave]) for i, d in enumerate(serie)]
        path = ' '.join(('M' if i == 0 else 'L') + f'{p[0]:.1f} {p[1]:.1f}' for i, p in enumerate(pts))
        area = path + f' L{pts[-1][0]:.1f} {H - pad_b} L{pts[0][0]:.1f} {H - pad_b} Z'
        camadas += f'<path d="{area}" fill="url(#rlArea{ci})"/>'
        camadas += (f'<path d="{path}" fill="none" stroke="{cor}" stroke-width="2" '
                    f'stroke-linecap="round" stroke-linejoin="round" filter="url(#rlGlow{ci})"/>')
        for i, p in enumerate(pts):
            if serie[i][chave] > 0:
                camadas += (f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="3" fill="{cor}" stroke="#0b2029" '
                            f'stroke-width="1"><title>{_rotulo}: {serie[i][chave]} em {serie[i]["data"]}</title></circle>')

    labels = ''
    for i, d in enumerate(serie):
        if i % 5 == 0 or i == n - 1:
            x = _xy(i, 0)[0]
            labels += (f'<text x="{x:.1f}" y="{H - 8}" text-anchor="middle" font-size="9.5" '
                       f'font-family="JetBrains Mono, monospace" fill="#6f8a93">{d["data"]}</text>')

    legenda = ''
    lx = pad_x
    for ci, (_chave, cor, rotulo) in enumerate(campos):
        legenda += (f'<rect x="{lx:.0f}" y="10" width="10" height="10" rx="2" fill="{cor}"/>'
                    f'<text x="{lx + 15:.0f}" y="19" font-size="10" font-family="JetBrains Mono, monospace" '
                    f'fill="#bcd3da">{rotulo}</text>')
        lx += 15 + 10 + len(rotulo) * 6.4
    legenda += (f'<text x="{W - pad_x:.0f}" y="19" text-anchor="end" font-size="10" '
                f'font-family="JetBrains Mono, monospace" fill="#6f8a93">{len(serie)} dias</text>')

    # min-w-[520px] é a mesma classe usada pelo _timeline_svg do dashboard —
    # garante que o Tailwind JIT (que escaneia apenas templates .html) a gere.
    return (f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" class="w-full min-w-[520px]">'
            + defs + legenda + camadas + labels + '</svg>')


def _resposta_csv(nome_arquivo):
    """Resposta CSV com BOM (Excel abre acentos corretamente) — mesmo padrão de contatos."""
    resposta = HttpResponse(content_type='text/csv; charset=utf-8')
    resposta['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    resposta.write('\ufeff')
    return resposta


def _csv_seguro(valor):
    """Previne injeção de fórmula no Excel (CSV injection)."""
    texto = str(valor or '')
    if texto.startswith(('=', '+', '-', '@')):
        return "'" + texto
    return texto


@web_login_required
def index(request):
    inicio, fim, label, chave = _periodo(request)
    tid = tenant_id_da_sessao(request)
    operador = _operador_do_filtro(request, tid)
    operador_id = operador.id if operador is not None else None
    kpis = _kpis(tid, inicio, fim, operador_id)
    produtividade = _produtividade(tid, inicio, fim, operador_id)
    serie = _serie_diaria(tid, inicio, fim, operador_id)
    tenant = Tenant.objects.filter(pk=tid).first() if tid is not None else None

    operadores = []
    if tid is not None:
        operadores = list(Usuario.objects.filter(
            tenant_id=tid, role__in=[ROLE_ADMIN_COMPANY, ROLE_OPERACIONAL],
        ).order_by('nome').values_list('id', 'nome'))

    return render(request, 'relatorios/index.html', {
        'kpis': kpis,
        'produtividade': produtividade,
        'periodo': chave,
        'periodo_label': label,
        'periodos': [
            ('hoje', 'Hoje'),
            ('7', 'Últimos 7 dias'),
            ('30', 'Últimos 30 dias'),
            ('mes', 'Mês corrente'),
        ],
        'operadores': operadores,
        'operador_atual': operador_id or '',
        'grafico_atividade': _linhas_svg(serie, [
            ('cpc', '#74b3c6', 'CPC'),
        ]),
        'empresa': tenant.nome if tenant else '—',
    })


@web_login_required
def exportar_csv(request):
    """Exporta o relatório gerencial em CSV (7.3.1)."""
    inicio, fim, label, chave = _periodo(request)
    tid = tenant_id_da_sessao(request)
    operador = _operador_do_filtro(request, tid)
    operador_id = operador.id if operador is not None else None
    kpis = _kpis(tid, inicio, fim, operador_id)
    produtividade = _produtividade(tid, inicio, fim, operador_id)

    resposta = _resposta_csv('relatorio-gerencial.csv')
    w = csv.writer(resposta, delimiter=';')
    w.writerow(['Relatório gerencial', _csv_seguro(label)])
    if operador is not None:
        w.writerow(['Operador', _csv_seguro(operador.nome)])
    w.writerow([])
    w.writerow(['Indicador', 'Valor'])
    w.writerow(['Base em cobrança (contatos com telefone)', kpis['base']])
    w.writerow(['Novos na base no período', kpis['base_novos']])
    w.writerow(['Contatos úteis realizados (CPC)', kpis['cpc']])
    w.writerow(['Retornos agendados', kpis['retornos']])
    w.writerow(['Chamadas no período', kpis['chamadas']])
    w.writerow([])
    w.writerow(['Produtividade por operador', '', '', ''])
    w.writerow(['Operador', 'Chamadas', 'Realizadas', 'Retornos'])
    for p in produtividade:
        w.writerow([
            _csv_seguro(p['nome']), p['chamadas'], p['realizadas'], p['retornos'],
        ])
    return resposta


@web_login_required
def exportar_pdf(request):
    """Exporta o relatório gerencial em PDF (7.3.2)."""
    from relatorios.pdf import gerar_relatorio_pdf

    inicio, fim, label, chave = _periodo(request)
    tid = tenant_id_da_sessao(request)
    operador = _operador_do_filtro(request, tid)
    operador_id = operador.id if operador is not None else None
    kpis = _kpis(tid, inicio, fim, operador_id)
    produtividade = _produtividade(tid, inicio, fim, operador_id)
    tenant = Tenant.objects.filter(pk=tid).first() if tid is not None else None
    operador_nome = operador.nome if operador is not None else None
    pdf = gerar_relatorio_pdf(tenant, label, kpis, produtividade, operador_nome=operador_nome)
    resposta = HttpResponse(pdf, content_type='application/pdf')
    resposta['Content-Disposition'] = 'attachment; filename="relatorio-gerencial.pdf"'
    return resposta
