"""Repository local do dashboard — lê Vales, Lojas, Membros e eventos.

Substitui o GprbRepository (PostgreSQL externo, desativado) nos blocos que
têm fonte local, mantendo os mesmos formatos de retorno para os templates:
KPIs, pirâmide de graus, agendamentos, ritos, faixas etárias, admissões,
potências, tempo de maçonaria e ranking de lojas.

Pagamentos de anuidade ainda não têm fonte local e retornam vazio/zerado em
vez de números fabricados.

`tenant_id=None` (admin_saas) enxerga todos os tenants; qualquer outro valor
restringe ao tenant da sessão.
"""

from datetime import date

from django.db.models import Count, F, Max, Q
from django.utils import timezone

from contatos.models import Loja, Membro, Vale


class LocalRepository:
    """Acesso aos dados locais do dashboard via ORM."""

    def __init__(self, tenant_id=None):
        self.tenant_id = tenant_id

    def _tenants(self):
        if self.tenant_id is None:
            return None
        return [self.tenant_id]

    def _vales(self):
        qs = Vale.objects.filter(status='ATIVA').order_by('nome', 'id')
        tenants = self._tenants()
        if tenants is not None:
            qs = qs.filter(tenant_id__in=tenants)
        return qs

    def _lojas(self):
        qs = Loja.objects.order_by('nome', 'id')
        tenants = self._tenants()
        if tenants is not None:
            qs = qs.filter(tenant_id__in=tenants)
        return qs

    def _membros_ativos(self):
        qs = Membro.objects.filter(situacao='ATIVO')
        tenants = self._tenants()
        if tenants is not None:
            qs = qs.filter(tenant_id__in=tenants)
        return qs

    def membros_ativos_por_faixa_de_graus(self):
        """Count active members once by their highest recorded degree."""
        faixas = [
            {'name': '4–14', 'label': 'Perfeição', 'minimo': 4, 'maximo': 14, 'total': 0},
            {'name': '15–18', 'label': 'Capítulo', 'minimo': 15, 'maximo': 18, 'total': 0},
            {'name': '19–30', 'label': 'Kadosh', 'minimo': 19, 'maximo': 30, 'total': 0},
            {'name': '31–32', 'label': 'Consistório', 'minimo': 31, 'maximo': 32, 'total': 0},
            {'name': '33', 'label': 'SCREAA', 'minimo': 33, 'maximo': 33, 'total': 0},
        ]
        maiores_graus = (
            self._membros_ativos()
            .filter(graus__tenant_id=F('tenant_id'))
            .annotate(grau_atual=Max('graus__grau__numero'))
            .order_by()
            .values_list('grau_atual', flat=True)
        )
        for grau in maiores_graus:
            for faixa in faixas:
                if faixa['minimo'] <= grau <= faixa['maximo']:
                    faixa['total'] += 1
                    break
        return [
            {
                'name': faixa['name'], 'label': faixa['label'],
                'total': faixa['total'],
            }
            for faixa in faixas
        ]

    def agendamento_lojas(self, limite=20):
        """Sessões realizadas × agendadas por loja, das duas fontes locais.

        - `agenda.EventoAgenda`: agenda de lembretes (FK de loja).
        - `tarefas.Evento`: Agenda de Sessões, onde os eventos são criados no
          CRM — `loja_id` é texto (pk numérico da Loja local ou código legado
          do banco externo). Eventos sem loja identificável não aparecem.
        """
        from agenda.models import EventoAgenda
        from tarefas.models import Evento

        hoje = timezone.localdate()
        contagens = {}

        def _conta(loja_nome, quando):
            item = contagens.setdefault(
                loja_nome, {'loja': loja_nome, 'realizadas': 0, 'agendadas': 0},
            )
            data = timezone.localtime(quando).date()
            if data < hoje:
                item['realizadas'] += 1
            else:
                item['agendadas'] += 1

        eventos_agenda = EventoAgenda.objects.select_related('loja')
        tenants = self._tenants()
        if tenants is not None:
            eventos_agenda = eventos_agenda.filter(tenant_id__in=tenants)
        for ev in eventos_agenda:
            _conta(ev.loja.nome, ev.data_hora)

        nomes_de_loja = {}
        for loja in Loja.objects.only('pk', 'nome', 'tenant_id'):
            nomes_de_loja[loja.pk] = loja
        for ev in Evento.objects.only('loja_id', 'data_inicio'):
            valor = str(ev.loja_id or '').strip()
            if not valor:
                continue
            if valor.isdigit() and int(valor) in nomes_de_loja:
                loja = nomes_de_loja[int(valor)]
                if tenants is not None and loja.tenant_id not in tenants:
                    continue
                _conta(loja.nome, ev.data_inicio)
            elif not valor.isdigit():
                # Código legado do banco externo (UUID): agrupado por código.
                _conta(f'Loja externa ({valor[:8]}…)', ev.data_inicio)

        resultado = []
        for item in contagens.values():
            agendadas = item['agendadas']
            item['cor'] = (
                'verde' if agendadas > 2 else (
                    'amarelo' if agendadas > 0 else 'vermelho'
                )
            )
            resultado.append(item)
        resultado.sort(
            key=lambda r: (-r['agendadas'], -r['realizadas'], r['loja']),
        )
        return resultado[:limite]

    # -- KPIs ------------------------------------------------------------
    def dashboard_kpis(self, ano=None):
        """Totais de lojas e membros do banco local."""
        if ano is None:
            ano = date.today().year
        lojas = self._lojas()
        membros = self._membros_ativos()
        return {
            'lojas_ativas': lojas.filter(situacao='ATIVA').count(),
            'lojas_total': lojas.count(),
            'membros_ativos': membros.count(),
            'membros_total': membros.count(),
            'novos_membros_ano': membros.filter(created_at__year=ano).count(),
        }

    # -- Pirâmide por Vale (membros ativos vinculados) -------------------
    def membros_por_potencia_vinculo(self, prefeitura_id=None):
        """Membros ativos distintos por Vale via vínculo com a Loja.

        Equivale ao `membros_por_potencia_vinculo` do GPRB, com Vale no lugar
        da Potência externa. Vales sem vínculo ficam fora.
        """
        vales = self._vales()
        if prefeitura_id:
            vales = vales.filter(pk=prefeitura_id)
        resultado = []
        for vale in vales:
            total = (
                self._membros_ativos()
                .filter(lojas__tenant_id=vale.tenant_id)
                .distinct()
                .count()
            )
            if total:
                resultado.append({'id': vale.pk, 'name': vale.nome, 'total': total})
        resultado.sort(key=lambda r: (-r['total'], r['name']))
        return resultado

    def membros_ativos_por_loja(self, prefeitura_id=None):
        """Membros ativos por Loja — alimenta o select do card Anuidade."""
        lojas = self._lojas()
        if prefeitura_id:
            vale = Vale.objects.filter(pk=prefeitura_id).first()
            if vale is None:
                return []
            lojas = lojas.filter(tenant_id=vale.tenant_id)
        resultado = []
        for loja in lojas.select_related('tenant'):
            try:
                vale_pk = loja.tenant.vales.pk
            except Vale.DoesNotExist:
                vale_pk = None
            resultado.append({
                'id': loja.pk,
                'name': loja.nome,
                'prefeitura_id': vale_pk,
                'total': loja.membros.filter(situacao='ATIVO').count(),
            })
        return resultado

    def anuidade_card(self, ano, prefeitura_id=None, loja_id=None):
        """Card Anuidade sem fonte local de pagamentos: totais reais, zeros.

        `total` soma os membros ativos vinculados no recorte; pagantes e
        pendentes ficam zerados porque o banco local não registra pagamentos.
        """
        potencias = self.membros_por_potencia_vinculo()
        lojas = self.membros_ativos_por_loja(prefeitura_id=prefeitura_id)
        if loja_id:
            lojas_do_filtro = [loja for loja in lojas if str(loja['id']) == str(loja_id)]
        else:
            lojas_do_filtro = lojas
        return {
            'pagantes': 0,
            'pendentes': 0,
            'percentual': 0,
            'total': sum(loja['total'] for loja in lojas_do_filtro),
            'lojas': lojas,
            'potencias': potencias,
        }

    # -- Perfil dos membros ----------------------------------------------
    def membros_por_rito(self):
        """Membros ativos por rito; sem rito cai em 'Não informado'."""
        agg = (
            self._membros_ativos()
            .values('rito')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        return [
            {'name': r['rito'] or 'Não informado', 'total': r['total']}
            for r in agg
        ]

    def membros_por_potencia(self):
        """Membros ativos por potência declarada no cadastro local."""
        agg = (
            self._membros_ativos()
            .values('potencia')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        return [
            {'name': r['potencia'] or 'Não declarado', 'total': r['total']}
            for r in agg
        ]

    def membros_por_idade_faixa(self):
        """Membros ativos por faixa etária (10 em 10 anos)."""
        hoje = date.today()
        faixas = {}
        for data_nascimento in self._membros_ativos().values_list(
            'data_nascimento', flat=True,
        ):
            if data_nascimento is None:
                continue
            idade = (
                hoje.year - data_nascimento.year
                - ((hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day))
            )
            if idade < 20:
                continue
            faixa_inicio = (idade // 10) * 10
            chave = f'{faixa_inicio}-{faixa_inicio + 9}'
            faixas[chave] = faixas.get(chave, 0) + 1
        return [{'label': k, 'total': v} for k, v in sorted(faixas.items())]

    def membros_por_tempo_maconaria(self):
        """Membros ativos por tempo de maçonaria (admissão ou cadastro)."""
        hoje = date.today()
        faixas = {}
        for membro in self._membros_ativos().values(
            'data_admissao', 'apresentacao_mx', 'created_at',
        ):
            data_ref = (
                membro['data_admissao']
                or membro['apresentacao_mx']
                or (membro['created_at'].date() if membro['created_at'] else None)
            )
            if data_ref is None:
                continue
            anos = (
                hoje.year - data_ref.year
                - ((hoje.month, hoje.day) < (data_ref.month, data_ref.day))
            )
            if anos < 1:
                chave = '< 1 ano'
            elif anos < 5:
                chave = '1-4 anos'
            elif anos < 10:
                chave = '5-9 anos'
            else:
                chave = '10+ anos'
            faixas[chave] = faixas.get(chave, 0) + 1
        return [{'label': k, 'total': v} for k, v in sorted(faixas.items())]

    def membros_por_mes(self, meses=36):
        """Admissões por mês (últimos N meses) via data_admissao ou cadastro."""
        por_mes = {}
        for membro in self._membros_ativos().values('data_admissao', 'created_at'):
            data_ref = membro['data_admissao'] or (
                membro['created_at'].date() if membro['created_at'] else None
            )
            if data_ref is None:
                continue
            por_mes[f'{data_ref.year}-{data_ref.month:02d}'] = (
                por_mes.get(f'{data_ref.year}-{data_ref.month:02d}', 0) + 1
            )
        hoje = date.today()
        labels, valores = [], []
        for i in range(meses - 1, -1, -1):
            ano, mes = hoje.year, hoje.month - i
            while mes <= 0:
                mes += 12
                ano -= 1
            chave = f'{ano}-{mes:02d}'
            labels.append(chave)
            valores.append(por_mes.get(chave, 0))
        return labels, valores

    def ranking_lojas(self, limite=10):
        """Ranking de lojas ativas por número de membros ativos."""
        lojas = self._lojas().filter(situacao='ATIVA').prefetch_related('membros')[:limite]
        ranqueadas = sorted(
            (
                {
                    'nome': loja.nome,
                    'total': loja.membros.filter(situacao='ATIVO').count(),
                }
                for loja in lojas
            ),
            key=lambda r: -r['total'],
        )[:limite]
        return [
            {'rank': i + 1, 'nome': r['nome'], 'total': r['total']}
            for i, r in enumerate(ranqueadas)
        ]
