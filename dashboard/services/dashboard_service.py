"""Service layer para o Dashboard.

Separa a logica de negocio (KPIs, calculos) do acesso a dados (repository)
e da camada de apresentacao (views). Cada metodo e uma unidade testavel.
"""

import logging
from datetime import date, datetime, time, timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from core.dominio import ORIGENS, PESOS_ETAPA, SEGS
from core.utils import brl, brl_curto
import psycopg

logger = logging.getLogger(__name__)


class DashboardService:
    """Service para calculo de KPIs e dados do dashboard."""

    def __init__(self, gprb_repo, negocios_qs, tid=None, nicho='saude'):
        self._gprb = gprb_repo
        self._negocios = negocios_qs
        self._tid = tid
        self._nicho = nicho

    def calcular_kpis(self):
        """Calcula todos os KPIs do dashboard."""
        from acesso.models import Tenant
        from recepcao.models import etapa_map_do_tenant

        hoje = date.today()
        inicio_mes = timezone.make_aware(datetime.combine(hoje.replace(day=1), time.min))
        inicio30 = timezone.make_aware(datetime.combine(hoje - timedelta(days=30), time.min))

        ativos = self._negocios.exclude(stage__in=['perdido', 'fechado'])
        fechados_mes = self._negocios.filter(stage='fechado', updated_at__gte=inicio_mes)
        nao_perdidos = self._negocios.exclude(stage='perdido')

        valor_funil = ativos.aggregate(s=Sum('valor'))['s'] or 0
        valor_fechados_mes = fechados_mes.aggregate(s=Sum('valor'))['s'] or 0
        conv = round(
            fechados_mes.count() / nao_perdidos.count() * 100
        ) if nao_perdidos.count() else 0

        mapa_etapas = etapa_map_do_tenant(self._tid, self._nicho)

        def _peso(stage):
            return float(mapa_etapas.get(stage, {}).get('peso', PESOS_ETAPA.get(stage, 0)))

        projetado = sum(float(n.valor) * _peso(n.stage) for n in nao_perdidos)
        valor_aberto = float(ativos.aggregate(s=Sum('valor'))['s'] or 0)
        projetado_aberto = sum(float(n.valor) * _peso(n.stage) for n in ativos)
        pct_potencial = round(projetado_aberto / valor_aberto * 100) if valor_aberto else 0

        tempos = [
            (f.updated_at - f.created_at).total_seconds() / 86400
            for f in fechados_mes
        ]
        tempo_medio = sum(tempos) / len(tempos) if tempos else None

        meta = Tenant.objects.filter(pk=self._tid).values_list(
            'meta_mensal', flat=True
        ).first() if self._tid else None
        meta_valor = float(meta) if meta else None
        meta_pct = round(
            float(valor_fechados_mes) / meta_valor * 100
        ) if meta_valor else None
        meta_bar_pct = min(100, meta_pct) if meta_pct is not None else None

        return {
            'ativos': ativos.count(),
            'novos_mes': self._negocios.filter(created_at__gte=inicio_mes).count(),
            'ultimos30': self._negocios.filter(created_at__gte=inicio30).count(),
            'valor_funil': _brl_curto(valor_funil),
            'fechados_qtd': fechados_mes.count(),
            'valor_fechados': _brl(valor_fechados_mes),
            'conversao': f'{conv}%',
            'receita_projetada': _brl_curto(projetado),
            'projetado_pct': pct_potencial,
            'tempo_medio_fechamento': (
                f'{tempo_medio:.1f}' if tempo_medio is not None else '—'
            ),
            'meta_valor': _brl(meta_valor) if meta_valor is not None else None,
            'meta_pct': meta_pct,
            'meta_bar_pct': meta_bar_pct,
        }

    def calcular_gprb_kpis(self):
        """Busca KPIs do banco GPRB (1 query via CTE)."""
        try:
            return self._gprb.dashboard_kpis(ano=date.today().year) or {}
        except (psycopg.Error, OSError, ValueError):
            logger.exception('Erro ao buscar KPIs GPRB')
            return {}

    def calcular_origens(self):
        """Negocios agrupados por origem (1 query)."""
        total = self._negocios.count()
        if total == 0:
            return []
        agg = self._negocios.values('contato__origem').annotate(
            count=Count('id'),
        )
        por_origem = []
        for r in agg:
            origem = r['contato__origem'] or 'Sem origem'
            if origem in ORIGENS or r['contato__origem'] is None:
                por_origem.append({
                    'nome': origem, 'count': r['count'],
                    'pct': round(r['count'] / total * 100),
                })
        return por_origem

    def calcular_segmentos(self):
        """Negocios agrupados por segmento (1 query)."""
        agg = self._negocios.values('contato__seg').annotate(
            total=Sum('valor')
        ).order_by('-total')
        por_segmento = []
        for r in agg:
            key = r['contato__seg']
            if key in SEGS:
                info = SEGS[key]
                total = float(r['total'] or 0)
                if total > 0:
                    por_segmento.append({
                        'label': info['label'], 'color': info['color'],
                        'total': total, 'total_label': brl_curto(total),
                    })
        return por_segmento

    def calcular_ocorrencias(self, stages):
        """Contagem de negocios por stage (1 query)."""
        ocorrencias = {s['key']: 0 for s in stages}
        agg = self._negocios.values('stage').annotate(cnt=Count('id'))
        for r in agg:
            ocorrencias[r['stage']] = r['cnt']
        return ocorrencias

    def calcular_timeline(self, hoje):
        """Timeline dos ultimos 30 dias (1 query)."""
        inicio = hoje - timedelta(days=29)
        agg = (
            self._negocios.filter(created_at__date__gte=inicio)
            .annotate(dia=TruncDate('created_at'))
            .values('dia')
            .annotate(count=Count('id'))
            .order_by('dia')
        )
        por_dia = {r['dia']: r['count'] for r in agg}
        timeline = []
        d = inicio
        while d <= hoje:
            timeline.append({
                'data': f'{d.day:02d}/{d.month:02d}',
                'valor': por_dia.get(d, 0),
            })
            d += timedelta(days=1)
        return timeline, max([p['valor'] for p in timeline] + [1])


def _brl(valor):
    """Formata valor em R$ (com casas decimais)."""
    return brl(valor)


def _brl_curto(valor):
    """Formata valor em R$ (sem casas decimais quando inteiro)."""
    return brl_curto(valor)
