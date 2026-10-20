"""KPIs do dashboard a partir do banco GPRB."""

from datetime import date

from core.gprb.connection import connect, resolve_tenant_code


def dashboard_kpis(tenant_code=None, ano=None):
    """Retorna todos os KPIs do dashboard em uma unica query ao banco GPRB.

    Substitui as ~5 queries separadas (total_membros x2, total_lojas_ativas,
    total_lojas_cadastradas, novos_membros_ano) por uma unica CTE.
    """
    tenant_code = resolve_tenant_code(tenant_code)
    if ano is None:
        ano = date.today().year
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
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
        row = cur.fetchone()
        return {
            'membros_total': row[0] or 0,
            'membros_ativos': row[1] or 0,
            'novos_membros_ano': row[2] or 0,
            'lojas_total': row[3] or 0,
            'lojas_ativas': row[4] or 0,
        }
    finally:
        conn.close()
