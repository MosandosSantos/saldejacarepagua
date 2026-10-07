"""Ranking de lojas e dados de presença no banco GPRB."""

import logging
from datetime import date, timedelta

from core.gprb.connection import connect

logger = logging.getLogger(__name__)


def _months_between(start, end=None):
    """Meses completos entre duas datas."""
    if end is None:
        end = date.today()
    if start is None:
        return 0
    if isinstance(start, str):
        try:
            start = date.fromisoformat(str(start)[:10])
        except ValueError:
            logger.warning('Erro ao converter data "%s" em _months_between', start)
            return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)


def _years_between(start, end=None):
    """Anos completos entre duas datas."""
    if end is None:
        end = date.today()
    if start is None:
        return 0
    if isinstance(start, str):
        try:
            start = date.fromisoformat(str(start)[:10])
        except ValueError:
            logger.warning('Erro ao converter data "%s" em _years_between', start)
            return 0
    years = end.year - start.year
    if (end.month, end.day) < (start.month, start.day):
        years -= 1
    return max(years, 0)


def ranking_lojas(tenant_code='GPRB', limite=10):
    """Retorna ranking das lojas com mais membros ativos.

    Retorna lista de dicts ordenada por total de membros (descendente):
        [{'nome': 'Loja X', 'total': 85, 'rank': 1}, ...]
    """
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COALESCE(l.\"nomeFantasia\", l.\"lojaMX\", 'Loja ' || l.numero::text), "  # nosec B608 - estrutura interna; valores parametrizados
            "COUNT(m.id) as total "
            "FROM loja l "
            "JOIN member m ON m.\"lojaId\" = l.id AND m.situacao = 'ATIVO' "
            "JOIN tenant t ON l.\"tenantId\" = t.id "
            "WHERE t.code = %s "
            "GROUP BY l.id, l.\"nomeFantasia\", l.\"lojaMX\", l.numero "
            "ORDER BY total DESC "
            "LIMIT %s",
            (tenant_code, limite),
        )
        resultado = []
        for i, r in enumerate(cur.fetchall(), 1):
            resultado.append({
                'rank': i,
                'nome': r[0],
                'total': r[1],
            })
        return resultado
    finally:
        conn.close()


def ranking_lojas_mx(tenant_code='GPRB', limite=10, anos=None):
    """Retorna ranking das lojas com mais membros MX.

    Se anos for informado, filtra por apresentacao_mx nos últimos N anos.
    Retorna lista de dicts:
        [{'nome': 'Loja X', 'total_mx': 32, 'primeira_mx': '10/01/2024', 'ultima_mx': '15/06/2026', 'rank': 1}, ...]
    """
    conn = connect()
    try:
        cur = conn.cursor()
        params = [tenant_code]
        where_extra = ''
        if anos is not None:
            data_inicio = date.today() - timedelta(days=anos * 365)
            where_extra = ' AND m."apresentacao_mx" >= %s'
            params.append(data_inicio)
        params.append(limite)
        sql = (  # nosec B608 - apenas estrutura interna; valores parametrizados
            "SELECT COALESCE(l.\"nomeFantasia\", l.\"lojaMX\", 'Loja ' || l.numero::text), "  # nosec B608 - estrutura interna; valores parametrizados
            "COUNT(m.id) as total_mx, "
            "MIN(m.\"apresentacao_mx\")::date as primeira_mx, "
            "MAX(m.\"apresentacao_mx\")::date as ultima_mx "
            "FROM loja l "
            "JOIN member m ON m.\"lojaId\" = l.id AND m.situacao = 'ATIVO' "
            "JOIN tenant t ON l.\"tenantId\" = t.id "
            "WHERE t.code = %s AND m.\"apresentacao_mx\" IS NOT NULL" + where_extra + " "
            "GROUP BY l.id, l.\"nomeFantasia\", l.\"lojaMX\", l.numero "
            "ORDER BY total_mx DESC "
            "LIMIT %s"
        )
        cur.execute(sql, tuple(params))
        resultado = []
        for i, r in enumerate(cur.fetchall(), 1):
            resultado.append({
                'rank': i,
                'nome': r[0],
                'total_mx': r[1],
                'primeira_mx': r[2].strftime('%d/%m/%Y') if r[2] else '—',
                'ultima_mx': r[3].strftime('%d/%m/%Y') if r[3] else '—',
            })
        return resultado
    finally:
        conn.close()


def _buscar_meetings(cur, tid, loja_id, prefeitura_id, data_inicio, data_fim):
    """Sessões realizadas no período (com filtros de loja/potência)."""
    params = [tid, data_inicio, data_fim]
    query = (
        'SELECT m.id, m."dataSessao"::date, m.tipo, m.titulo '
        'FROM meeting m '
        'WHERE m."tenantId" = %s '
        'AND m."dataSessao"::date >= %s AND m."dataSessao"::date <= %s '
        'AND m."dataSessao"::date <= CURRENT_DATE '
    )
    if loja_id:
        query += 'AND m."lojaId" = %s '
        params.append(loja_id)
    if prefeitura_id:
        query += ('AND m."lojaId" IN '
                  '(SELECT l2.id FROM loja l2 WHERE l2."prefeituraId" = %s) ')
        params.append(prefeitura_id)
    query += 'ORDER BY m."dataSessao" ASC'
    cur.execute(query, params)
    meetings = [{'id': r[0], 'data': r[1].isoformat() if r[1] else '',
                 'tipo': r[2] or '', 'titulo': r[3] or ''}
                for r in cur.fetchall()]
    return meetings, [m['id'] for m in meetings]


def _buscar_members(cur, tid, loja_id, prefeitura_id):
    """Membros ativos com anuidade do exercício de referência (out→dez usa ano+1)."""
    hoje = date.today()
    ano_ref = hoje.year + 1 if hoje.month >= 10 else hoje.year
    params = [ano_ref, tid, 'ATIVO']
    query = (
        'SELECT m.id, m."nomeCompleto", '
        'COALESCE(m."apresentacao_mx", m."apresentacao_ec"), '
        'm."dataNascimento", '
        'EXISTS('
        '  SELECT 1 FROM payment_status ps '
        '  JOIN payment_period pp ON ps."periodId" = pp.id '
        '  WHERE ps."memberId" = m.id AND pp.type = \'ANNUAL\' '
        '  AND pp.year = %s AND ps.status = \'PAID\''
        ') as anuidade_ok, '
        'COALESCE(l."nomeFantasia", \'Loja \' || l.numero::text) as loja_nome, '
        'p.sigla as prefeitura_sigla '
        'FROM member m '
        'LEFT JOIN loja l ON m."lojaId" = l.id '
        'LEFT JOIN prefeitura p ON l."prefeituraId" = p.id '
        'WHERE m."tenantId" = %s AND m.situacao = %s '
    )
    if loja_id:
        query += 'AND m."lojaId" = %s '
        params.append(loja_id)
    if prefeitura_id:
        query += 'AND l."prefeituraId" = %s '
        params.append(prefeitura_id)
    query += 'ORDER BY m."nomeCompleto" ASC'
    cur.execute(query, params)
    members = []
    for r in cur.fetchall():
        recepcao = r[2]
        if recepcao and hasattr(recepcao, 'date'):
            recepcao = recepcao.date()
        members.append({
            'id': r[0], 'nome': r[1] or '',
            'recepcao': recepcao.isoformat() if recepcao else '',
            'data_nascimento': r[3].isoformat() if r[3] else '',
            'classe_abbr': '', 'classe_nome': '',
            'anuidade_ok': bool(r[4]),
            'loja_nome': r[5] or '',
            'prefeitura_sigla': r[6] or '',
        })
    return members


def _buscar_attendances(cur, tid, meeting_ids, member_ids):
    """Presenças por (memberId, meetingId) em lotes de 50."""
    attendances = {}
    if not (meeting_ids and member_ids):
        return attendances
    for i in range(0, len(member_ids), 50):
        batch = member_ids[i:i + 50]
        placeholders = ','.join(['%s'] * len(batch))
        sql = (
            'SELECT "memberId", "meetingId", status '
            'FROM attendance '
            'WHERE "tenantId" = %s '
            'AND "memberId" IN (' + placeholders + ')'
        )
        cur.execute(sql, [tid] + batch)  # nosec B608 - placeholders '%s' literais; valores parametrizados
        for r in cur.fetchall():
            attendances[f'{r[0]}_{r[1]}'] = r[2]
    return attendances


def _calcular_stats(members, meeting_ids, attendances, total_meetings):
    """Estatísticas de presença por membro (presente/falta/percentual)."""
    stats = []
    for m in members:
        total_present = sum(
            1 for mid in meeting_ids
            if attendances.get(f'{m["id"]}_{mid}') == 'PRESENTE'
        )
        total_absent = sum(
            1 for mid in meeting_ids
            if attendances.get(f'{m["id"]}_{mid}') == 'FALTA'
        )
        percentage = round(total_present / total_meetings * 100) if total_meetings > 0 else 0
        stats.append({
            'memberId': m['id'],
            'totalPresent': total_present,
            'totalAbsent': total_absent,
            'totalRecorded': total_meetings,
            'percentage': percentage,
        })
    return stats


def ranking_dados(tenant_code='GPRB', classe='MX', loja_id=None, prefeitura_id=None,
                  data_inicio=None, data_fim=None):
    """Retorna dados para o ranking de presença (orquestra as 4 etapas).

        Retorna dict com:
            meetings: [{id, data, tipo, titulo}]
            members: [{id, nome, recepcao, data_nascimento, classe_abbr, classe_nome, anuidade_ok}]
            attendances: {memberId_meetingId: status}
            memberStats: [{memberId, totalPresent, totalRecorded, totalAbsent, percentage}]
        """
    conn = connect()
    if conn is None:
        return {'meetings': [], 'members': [], 'attendances': {}, 'memberStats': []}
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tenant WHERE code = %s", (tenant_code,))
        tid = cur.fetchone()[0]

        if data_inicio is None:
            data_inicio = date(date.today().year - 2, 1, 1)
        if data_fim is None:
            data_fim = date.today()

        meetings, meeting_ids = _buscar_meetings(
            cur, tid, loja_id, prefeitura_id, data_inicio, data_fim)
        members = _buscar_members(cur, tid, loja_id, prefeitura_id)
        attendances = _buscar_attendances(cur, tid, meeting_ids, [m['id'] for m in members])
        member_stats = _calcular_stats(members, meeting_ids, attendances, len(meetings))

        return {
            'meetings': meetings,
            'members': members,
            'attendances': attendances,
            'memberStats': member_stats,
        }
    finally:
        conn.close()
