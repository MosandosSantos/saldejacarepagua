"""Repository layer para queries ao banco GPRB (PostgreSQL externo).

Separa o acesso a dados do banco GPRB da logica de negocio.
Cada metodo representa uma query isolada e testavel.
"""

import logging
from datetime import date

logger = logging.getLogger(__name__)


class GprbRepository:
    """Acesso a dados do banco GPRB via psycopg3."""

    def __init__(self, connect_fn=None):
        self._connect = connect_fn or self._default_connect

    def _default_connect(self):
        from core.gprb import connect
        return connect()

    def _fetch_all(self, sql, params=None):
        """Executa query e retorna lista de dicts."""
        conn = self._connect()
        if conn is None:
            return []
        try:
            cur = conn.cursor()
            cur.execute(sql, params or ())
            columns = [desc[0] for desc in cur.description] if cur.description else []
            return [dict(zip(columns, row, strict=False)) for row in cur.fetchall()]
        finally:
            conn.close()

    def _fetch_one(self, sql, params=None):
        """Executa query e retorna primeiro row ou None."""
        conn = self._connect()
        if conn is None:
            return None
        try:
            cur = conn.cursor()
            cur.execute(sql, params or ())
            row = cur.fetchone()
            if row and cur.description:
                return dict(zip([d[0] for d in cur.description], row, strict=False))
            # description=None (modo degradado) => sem resultado; a tupla crua
            # do dummy quebraria os consumidores que esperam dict/None.
            return row if cur.description else None
        finally:
            conn.close()

    def dashboard_kpis(self, tenant_code='GPRB', ano=None):
        """KPIs unificados do dashboard (1 query com CTE)."""
        if ano is None:
            ano = date.today().year
        return self._fetch_one(
            """
            WITH membros_cte AS (
                SELECT
                    COUNT(*) AS total_membros,
                    COUNT(*) FILTER (WHERE m.situacao = 'ATIVO') AS membros_ativos,
                    COUNT(*) FILTER (
                        WHERE m.situacao = 'ATIVO'
                        AND EXTRACT(YEAR FROM m."createdAt") = %s
                    ) AS novos_membros_ano
                FROM member m
                JOIN tenant t ON m."tenantId" = t.id
                WHERE t.code = %s
            ),
            lojas_cte AS (
                SELECT
                    COUNT(*) AS total_lojas,
                    COUNT(*) FILTER (WHERE l.situacao = 'ATIVA') AS lojas_ativas
                FROM loja l
                JOIN tenant t ON l."tenantId" = t.id
                WHERE t.code = %s
            )
            SELECT
                m.total_membros, m.membros_ativos, m.novos_membros_ano,
                l.total_lojas, l.lojas_ativas
            FROM membros_cte m, lojas_cte l
            """,
            (ano, tenant_code, tenant_code),
        )

    def membros_por_situacao(self, tenant_code='GPRB', apenas_ativos=True, ano=None):
        """Contagem de membros por situacao (classes nao se aplicam ao projeto)."""
        conditions = ["t.code = %s"]
        params = [tenant_code]
        if apenas_ativos:
            conditions.append("m.situacao = 'ATIVO'")
        else:
            conditions.append("m.situacao IS DISTINCT FROM 'ATIVO'")
        if ano is not None:
            conditions.append('EXTRACT(YEAR FROM m."createdAt") = %s')
            params.append(ano)
        where = ' AND '.join(conditions)
        sql = (
            "SELECT m.situacao AS name, COUNT(m.id) as total "  # nosec B608 - fragmentos literais; valores parametrizados
            "FROM member m "
            "JOIN tenant t ON m.\"tenantId\" = t.id "
            "WHERE " + where + " "
            "GROUP BY m.situacao "
            "ORDER BY total DESC"
        )
        return self._fetch_all(sql, params)  # nosec B608 - apenas estrutura interna; valores parametrizados

    def membros_por_rito(self, tenant_code='GPRB'):
        """Contagem de membros ativos por rito."""
        return self._fetch_all(
            "SELECT m.rito, COUNT(*) as total "
            "FROM member m "
            "JOIN tenant t ON m.\"tenantId\" = t.id "
            "WHERE t.code = %s AND m.situacao = 'ATIVO' "
            "AND m.rito IS NOT NULL AND m.rito != '' "
            "GROUP BY m.rito ORDER BY total DESC",
            (tenant_code,),
        )

    def membros_por_idade_faixa(self, tenant_code='GPRB'):
        """Contagem de membros ativos por faixa etaria."""
        rows = self._fetch_all(
            'SELECT m."dataNascimento" '
            'FROM member m '
            'JOIN tenant t ON m."tenantId" = t.id '
            'WHERE t.code = %s AND m.situacao = %s '
            'AND m."dataNascimento" IS NOT NULL',
            (tenant_code, 'ATIVO'),
        )
        hoje = date.today()
        faixas = {}
        for row in rows:
            dn = row['dataNascimento']
            if hasattr(dn, 'date'):
                dn = dn.date()
            idade = hoje.year - dn.year - ((hoje.month, hoje.day) < (dn.month, dn.day))
            if idade < 20:
                continue
            faixa_inicio = (idade // 10) * 10
            chave = f'{faixa_inicio}-{faixa_inicio + 9}'
            faixas[chave] = faixas.get(chave, 0) + 1
        return [{'label': k, 'total': v} for k, v in sorted(faixas.items())]

    def membros_por_potencia(self, tenant_code='GPRB'):
        """Contagem de membros ativos por potencia (coluna potencia_simbolismo)."""
        return self._fetch_all(
            "SELECT CASE WHEN m.\"potencia_simbolismo\" IS NULL OR m.\"potencia_simbolismo\" = '' "
            "THEN 'Nao declarado' ELSE m.\"potencia_simbolismo\" END as name, "
            "COUNT(*) as total "
            "FROM member m "
            "JOIN tenant t ON m.\"tenantId\" = t.id "
            "WHERE t.code = %s AND m.situacao = 'ATIVO' "
            "GROUP BY 1 ORDER BY total DESC",
            (tenant_code,),
        )

    def membros_por_potencia_vinculo(self, tenant_code='GPRB', prefeitura_id=None):
        """Contagem de membros ativos por Potencia (prefeitura) via vinculacao.

        Percorre member_loja -> loja -> prefeitura: N:N, um membro pode estar
        ligado a mais de uma loja, logo conta-se o vinculo (um membro pode
        aparecer em mais de uma Potencia e o total excede o de membros).
        Potencias sem membros vinculados ficam fora do resultado.
        `prefeitura_id` restringe a uma Potencia (para o card Anuidade).
        """
        where = "WHERE t.code = %s AND m.situacao = 'ATIVO' AND p.id IS NOT NULL"
        params = [tenant_code]
        if prefeitura_id:
            where += ' AND p.id = %s'
            params.append(prefeitura_id)
        return self._fetch_all(
            "SELECT p.id, p.nome AS name, COUNT(DISTINCT ml.\"memberId\") AS total "
            "FROM member_loja ml "
            "JOIN loja l ON ml.\"lojaId\" = l.id "
            "LEFT JOIN prefeitura p ON l.\"prefeituraId\" = p.id "
            "JOIN member m ON ml.\"memberId\" = m.id "
            "JOIN tenant t ON m.\"tenantId\" = t.id "
            + where +
            " GROUP BY p.id, p.nome ORDER BY total DESC, p.nome",
            params,
        )

    def membros_ativos_por_loja(self, tenant_code='GPRB', prefeitura_id=None):
        """Contagem de vinculacoes ativas por loja (COUNT DISTINCT memberId).

        Total simples por loja: membro ligado a N lojas soma 1 em cada —
        o somatorio pode exceder o numero de membros. `prefeitura_id`
        restringe as lojas de uma Potencia (card Anuidade).
        """
        where = "WHERE t.code = %s AND m.situacao = 'ATIVO'"
        params = [tenant_code]
        if prefeitura_id:
            where += ' AND l.\"prefeituraId\" = %s'
            params.append(prefeitura_id)
        return self._fetch_all(
            'SELECT l.id, '
            "COALESCE(l.\"nomeFantasia\", l.\"lojaMX\", 'Loja ' || COALESCE(l.numero::text, '')) AS name, "
            'l.\"prefeituraId\" AS prefeitura_id, '
            'COUNT(DISTINCT ml.\"memberId\") AS total '
            'FROM member_loja ml '
            'JOIN loja l ON ml.\"lojaId\" = l.id '
            'JOIN member m ON ml.\"memberId\" = m.id '
            'JOIN tenant t ON m.\"tenantId\" = t.id '
            + where +
            ' GROUP BY l.id, l.\"nomeFantasia\", l.\"lojaMX\", l.numero, l.\"prefeituraId\" '
            'ORDER BY total DESC, name',
            params,
        )

    def anuidade_card(self, ano, tenant_code='GPRB', prefeitura_id=None, loja_id=None):
        """Dados do card Anuidade — pagantes/pendentes + total simples por loja.

        Pagamentos contam VINCULOS (membro em 2 lojas com anuidade paga soma
        2): o percentual sai igual ao global (a cobranca e do membro), mas os
        totais seguem a regra "soma simples das lojas". `total` sao membros
        ativos vinculados (por loja) — inclusive os sem cobranca registrada.
        `lojas` volta completo no escopo (para repopular o select de lojas).
        """
        where = "WHERE t.code = %s AND pp.type = 'ANNUAL' AND pp.year = %s "
        where += "AND m.situacao = 'ATIVO'"
        params = [tenant_code, ano]
        if prefeitura_id:
            where += ' AND l."prefeituraId" = %s'
            params.append(prefeitura_id)
        if loja_id:
            where += ' AND l.id = %s'
            params.append(loja_id)
        rows = self._fetch_all(
            'SELECT ps.status, COUNT(*) AS quantidade '
            'FROM payment_status ps '
            'JOIN payment_period pp ON ps.\"periodId\" = pp.id '
            'JOIN tenant t ON pp.\"tenantId\" = t.id '
            'JOIN member m ON m.id = ps.\"memberId\" '
            'JOIN member_loja ml ON ml.\"memberId\" = m.id '
            'JOIN loja l ON ml.\"lojaId\" = l.id '
            + where +
            ' GROUP BY ps.status',
            params,
        )
        pagamentos = {r['status']: r['quantidade'] for r in rows}
        pagantes = pagamentos.get('PAID', 0)
        pendentes = pagamentos.get('PENDING', 0)
        total_pagamentos = pagantes + pendentes
        # Opções completas do select de Potências (independem do recorte de loja)
        potencias = self.membros_por_potencia_vinculo(tenant_code)
        lojas = self.membros_ativos_por_loja(tenant_code, prefeitura_id=prefeitura_id)
        if loja_id:
            lojas_do_filtro = [loja for loja in lojas if str(loja['id']) == str(loja_id)]
        else:
            lojas_do_filtro = lojas
        return {
            'pagantes': pagantes, 'pendentes': pendentes,
            'percentual': round(pagantes / total_pagamentos * 100) if total_pagamentos else 0,
            'total': sum(loja['total'] for loja in lojas_do_filtro),
            'lojas': lojas,  # lista completa do escopo — repopula o select
            'potencias': potencias,
        }

    def membros_por_tempo_maconaria(self, tenant_code='GPRB'):
        """Contagem de membros ativos por tempo de masonaria."""
        rows = self._fetch_all(
            'SELECT m."dataAdmissao", m."apresentacao_mx", m."createdAt" '
            'FROM member m '
            'JOIN tenant t ON m."tenantId" = t.id '
            'WHERE t.code = %s AND m.situacao = %s',
            (tenant_code, 'ATIVO'),
        )
        hoje = date.today()
        faixas = {}
        for row in rows:
            data_ref = row.get('dataAdmissao') or row.get('apresentacao_mx') or row.get('createdAt')
            if data_ref is None:
                continue
            if hasattr(data_ref, 'date'):
                data_ref = data_ref.date()
            anos = hoje.year - data_ref.year - ((hoje.month, hoje.day) < (data_ref.month, data_ref.day))
            if anos < 1:
                faixas['< 1 ano'] = faixas.get('< 1 ano', 0) + 1
            elif anos < 5:
                faixas['1-4 anos'] = faixas.get('1-4 anos', 0) + 1
            elif anos < 10:
                faixas['5-9 anos'] = faixas.get('5-9 anos', 0) + 1
            else:
                faixas['10+ anos'] = faixas.get('10+ anos', 0) + 1
        return [{'label': k, 'total': v} for k, v in sorted(faixas.items())]

    def membros_por_mes(self, tenant_code='GPRB', meses=36):
        """Membros admitidos por mes (ultimos N meses)."""
        conn = self._connect()
        try:
            cur = conn.cursor()
            interval_sql = f"'{meses} months'"
            cur.execute(
                'SELECT TO_CHAR(COALESCE(m."dataAdmissao", m."apresentacao_mx", m."createdAt"), '
                "'YYYY-MM'" + ') as mes, COUNT(*) as total '
                'FROM member m '
                'JOIN tenant t ON m."tenantId" = t.id '
                'WHERE t.code = %s '
                'AND COALESCE(m."dataAdmissao", m."apresentacao_mx", m."createdAt") '
                '>= NOW() - INTERVAL ' + interval_sql + ' '
                'GROUP BY mes ORDER BY mes',
                (tenant_code,),
            )
            dados = {row[0]: row[1] for row in cur.fetchall()}
        finally:
            conn.close()
        hoje = date.today()
        labels = []
        valores = []
        for i in range(meses - 1, -1, -1):
            ano = hoje.year
            mes = hoje.month - i
            while mes <= 0:
                mes += 12
                ano -= 1
            chave = f'{ano}-{mes:02d}'
            labels.append(chave)
            valores.append(dados.get(chave, 0))
        return labels, valores

    def ranking_lojas(self, tenant_code='GPRB'):
        """Ranking de lojas por numero de membros."""
        rows = self._fetch_all(
            "SELECT COALESCE(l.\"nomeFantasia\", l.\"lojaMX\", 'Loja ' || l.numero::text) as name, "
            "COUNT(m.id) as total "
            "FROM loja l "
            "JOIN tenant t ON l.\"tenantId\" = t.id "
            "LEFT JOIN member m ON m.\"lojaId\" = l.id AND m.situacao = 'ATIVO' "
            "WHERE t.code = %s AND l.situacao = 'ATIVA' "
            "GROUP BY l.id ORDER BY total DESC LIMIT 10",
            (tenant_code,),
        )
        return [
            {'rank': i + 1, 'nome': r['name'], 'total': r['total']}
            for i, r in enumerate(rows)
        ]

    def ranking_lojas_mx(self, tenant_code='GPRB', anos=3):
        """Ranking de lojas por novos mestres (apresentacao_mx) nos ultimos N anos."""
        ano_atual = date.today().year
        rows = self._fetch_all(
            "SELECT COALESCE(l.\"nomeFantasia\", l.\"lojaMX\", 'Loja ' || l.numero::text) as name, "
            "COUNT(m.id) as total "
            "FROM member m "
            "JOIN loja l ON m.\"lojaId\" = l.id "
            "JOIN tenant t ON m.\"tenantId\" = t.id "
            "WHERE t.code = %s AND m.\"apresentacao_mx\" IS NOT NULL "
            "AND EXTRACT(YEAR FROM m.\"apresentacao_mx\") >= %s "
            "GROUP BY l.id, 1 ORDER BY total DESC LIMIT 10",
            (tenant_code, ano_atual - anos),
        )
        return [
            {'rank': i + 1, 'nome': r['name'], 'total_mx': r['total']}
            for i, r in enumerate(rows)
        ]

    def proximas_sessoes(self, tenant_code='GPRB'):
        """Proximas sessoes das lojas (tabela meeting)."""
        rows = self._fetch_all(
            "SELECT m.\"dataSessao\", m.tipo, "
            "COALESCE(l.\"nomeFantasia\", l.\"lojaMX\", 'Loja ' || l.numero::text) as loja "
            "FROM meeting m "
            "JOIN loja l ON m.\"lojaId\" = l.id "
            "JOIN tenant t ON m.\"tenantId\" = t.id "
            "WHERE t.code = %s AND m.\"dataSessao\" >= CURRENT_DATE "
            "ORDER BY m.\"dataSessao\" LIMIT 6",
            (tenant_code,),
        )
        meses = ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ']
        return [
            {
                'dia': r['dataSessao'].day,
                'mes': meses[r['dataSessao'].month - 1],
                'data_fmt': r['dataSessao'].strftime('%d/%m/%Y'),
                'loja': r['loja'],
                'tipo': r['tipo'] or '',
            }
            for r in rows
        ]

    def agendamento_lojas(self, tenant_code='GPRB'):
        """Sessoes realizadas vs agendadas por loja (tabela meeting)."""
        rows = self._fetch_all(
            "SELECT COALESCE(l.\"nomeFantasia\", l.\"lojaMX\", 'Loja ' || l.numero::text) as loja, "
            "COUNT(*) FILTER (WHERE m.\"dataSessao\" < CURRENT_DATE) as realizadas, "
            "COUNT(*) FILTER (WHERE m.\"dataSessao\" >= CURRENT_DATE) as agendadas "
            "FROM meeting m "
            "JOIN loja l ON m.\"lojaId\" = l.id "
            "JOIN tenant t ON m.\"tenantId\" = t.id "
            "WHERE t.code = %s "
            "GROUP BY l.id ORDER BY agendadas DESC, realizadas DESC LIMIT 20",
            (tenant_code,),
        )
        resultado = []
        for r in rows:
            agendadas = r['agendadas'] or 0
            cor = 'verde' if agendadas > 2 else ('amarelo' if agendadas > 0 else 'vermelho')
            resultado.append({
                'loja': r['loja'],
                'realizadas': r['realizadas'] or 0,
                'agendadas': agendadas,
                'cor': cor,
            })
        return resultado
