"""Conexão ao banco de dados SAL GPRB (PostgreSQL compartilhado).

Fornece funções para consultar membros, lojas e outros dados do sistema
de gestão de lojas maônicas. A conexão é feita via psycopg3 com pooling
simples (reconnect a cada chamada — suficiente para consultas pontuais).
"""
import logging
import os
import urllib.parse

import bcrypt
import psycopg

logger = logging.getLogger(__name__)


def _get_password():
    """Retorna a senha do PostgreSQL a partir da variável de ambiente ou .env local."""
    pw = os.environ.get('GPRB_DB_PASSWORD')
    if pw:
        return pw
    # Fallback: lê do .env do projeto
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith('PGPASSWORD='):
                    return line.split('=', 1)[1]
    return None


def connect():
    """Abre uma conexão com o banco saldogprb e retorna o objeto psycopg."""
    password = _get_password()
    return psycopg.connect(
        host=os.environ.get('GPRB_DB_HOST', '127.0.0.1'),
        port=int(os.environ.get('GPRB_DB_PORT', '5432')),
        dbname=os.environ.get('GPRB_DB_NAME', 'saldogprb'),
        user=os.environ.get('GPRB_DB_USER', 'postgres'),
        password=password,
        # S2.3 — producao usa PostgreSQL remoto: exige TLS quando o servidor
        # suporta ('prefer' mantem dev local sem TLS) e nunca trava esperando
        # o banco (timeout curto evita worker preso).
        sslmode=os.environ.get('GPRB_DB_SSLMODE', 'prefer'),
        connect_timeout=int(os.environ.get('GPRB_DB_TIMEOUT', '10')),
    )


def membros_por_classe(tenant_code='GPRB', apenas_ativos=True, ano=None):
    """Retorna a contagem de membros agrupados por classe (class.name / class.abbreviation).

    Retorna lista de dicts:
        [{'name': 'Mestre de Santo André', 'abbr': 'MX', 'total': 143}, ...]

    Parâmetros:
        tenant_code: código do tenant (default 'GPRB')
        apenas_ativos: se True, filtra por situacao='ATIVO'
        ano: se informado, filtra por dataInscricao no ano dado
    """
    conn = connect()
    try:
        cur = conn.cursor()

        conditions = ["t.code = %s"]
        params = [tenant_code]

        if apenas_ativos:
            conditions.append("m.situacao = 'ATIVO'")

        if ano is not None:
            conditions.append('EXTRACT(YEAR FROM m."createdAt") = %s')
            params.append(ano)

        where = ' AND '.join(conditions)

        cur.execute(f"""
            SELECT c.name, c.abbreviation, COUNT(m.id) as total
            FROM member m
            JOIN class c ON m.class_id = c.id
            JOIN tenant t ON m."tenantId" = t.id
            WHERE {where}
            GROUP BY c.name, c.abbreviation
            ORDER BY c.name
        """, params)

        return [
            {'name': row[0], 'abbr': row[1], 'total': row[2]}
            for row in cur.fetchall()
        ]
    finally:
        conn.close()


def total_membros(tenant_code='GPRB', apenas_ativos=True, ano=None):
    """Retorna o total de membros."""
    conn = connect()
    try:
        cur = conn.cursor()

        conditions = ["t.code = %s"]
        params = [tenant_code]

        if apenas_ativos:
            conditions.append("m.situacao = 'ATIVO'")

        if ano is not None:
            conditions.append('EXTRACT(YEAR FROM m."createdAt") = %s')
            params.append(ano)

        where = ' AND '.join(conditions)

        cur.execute(f"""
            SELECT COUNT(m.id)
            FROM member m
            JOIN tenant t ON m."tenantId" = t.id
            WHERE {where}
        """, params)

        return cur.fetchone()[0]
    finally:
        conn.close()


def total_lojas_ativas(tenant_code='GPRB'):
    """Retorna o total de lojas ativas no banco GPRB."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT COUNT(*) FROM loja l '
            'JOIN tenant t ON l."tenantId" = t.id '
            'WHERE t.code = %s AND l.situacao = %s',
            (tenant_code, 'ATIVA'),
        )
        return cur.fetchone()[0]
    finally:
        conn.close()


def total_lojas_cadastradas(tenant_code='GPRB'):
    """Retorna o total de lojas cadastradas (todas) no banco GPRB."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT COUNT(*) FROM loja l '
            'JOIN tenant t ON l."tenantId" = t.id '
            'WHERE t.code = %s',
            (tenant_code,),
        )
        return cur.fetchone()[0]
    finally:
        conn.close()


def membros_por_mes(tenant_code='GPRB', meses=36):
    """Retorna a quantidade de membros admitidos por mes.

    Usa COALESCE(dataAdmissao, apresentacao_mx, createdAt) como data de admissao.
    """
    from datetime import date

    conn = connect()
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

    # Gera lista dos ultimos N meses
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


def novos_membros_ano(tenant_code='GPRB', ano=None):
    """Retorna o total de membros novos no ano corrente (cadastrados no sistema)."""
    if ano is None:
        from datetime import date
        ano = date.today().year
    return total_membros(tenant_code=tenant_code, apenas_ativos=True, ano=ano)


def anuidade_ano_referencia():
    """Ano de referência da anuidade: mês ≤ 9 → ano corrente; mês ≥ 10 → ano corrente + 1."""
    from datetime import date
    hoje = date.today()
    if hoje.month >= 10:
        return hoje.year + 1
    return hoje.year


def anualidade_resumo(tenant_code='GPRB', ano=None):
    """Retorna resumo da anualidade: pagantes, pendentes, total, percentual."""
    if ano is None:
        ano = anuidade_ano_referencia()
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT ps.status, COUNT(*) '
            'FROM payment_status ps '
            'JOIN payment_period pp ON ps."periodId" = pp.id '
            'JOIN tenant t ON pp."tenantId" = t.id '
            'WHERE t.code = %s AND pp.type = %s AND pp.year = %s '
            'GROUP BY ps.status',
            (tenant_code, 'ANNUAL', ano),
        )
        dados = {r[0]: r[1] for r in cur.fetchall()}
    finally:
        conn.close()
    pagantes = dados.get('PAID', 0)
    pendentes = dados.get('PENDING', 0)
    total = pagantes + pendentes
    percentual = round(pagantes / total * 100) if total > 0 else 0
    return {
        'pagantes': pagantes,
        'pendentes': pendentes,
        'total': total,
        'percentual': percentual,
    }


def membros_por_rito(tenant_code='GPRB'):
    """Retorna a contagem de membros ativos agrupados por rito.

    Exclui registros com rito NULL/vazio.
    Retorna lista de dicts:
        [{'name': 'REAA', 'total': 14}, ...]
    """
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT m.rito, COUNT(*) as total "
            "FROM member m "
            "JOIN tenant t ON m.\"tenantId\" = t.id "
            "WHERE t.code = %s AND m.situacao = 'ATIVO' "
            "AND m.rito IS NOT NULL AND m.rito != '' "
            "GROUP BY m.rito ORDER BY total DESC",
            (tenant_code,),
        )
        return [
            {'name': row[0], 'total': row[1]}
            for row in cur.fetchall()
        ]
    finally:
        conn.close()


def membros_por_idade_faixa(tenant_code='GPRB'):
    """Retorna a contagem de membros ativos por faixa etária (10 anos, a partir de 20).

    Exclui membros sem dataNascimento.
    Retorna lista de dicts:
        [{'label': '20-29', 'total': 12}, {'label': '30-39', 'total': 25}, ...]
    """
    from datetime import date

    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT m."dataNascimento" '
            'FROM member m '
            'JOIN tenant t ON m."tenantId" = t.id '
            'WHERE t.code = %s AND m.situacao = %s '
            'AND m."dataNascimento" IS NOT NULL',
            (tenant_code, 'ATIVO'),
        )
        hoje = date.today()
        faixas = {}
        for row in cur.fetchall():
            dn = row[0]
            if hasattr(dn, 'date'):
                dn = dn.date()
            idade = hoje.year - dn.year - ((hoje.month, hoje.day) < (dn.month, dn.day))
            if idade < 20:
                continue
            faixa_inicio = (idade // 10) * 10
            chave = f'{faixa_inicio}-{faixa_inicio + 9}'
            faixas[chave] = faixas.get(chave, 0) + 1
        # Ordena por faixa
        resultado = [{'label': k, 'total': v} for k, v in sorted(faixas.items(), key=lambda x: int(x[0].split('-')[0]))]
        return resultado
    finally:
        conn.close()


def membros_por_potencia(tenant_code='GPRB'):
    """Retorna a contagem de membros ativos agrupados por potência do simbolismo.

    Inclui 'Não declarado' para registros com potencia_simbolismo NULL/vazio.
    Retorna lista de dicts:
        [{'name': 'Potência X', 'total': 10}, ...]
    """
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT CASE WHEN m.\"potencia_simbolismo\" IS NULL OR m.\"potencia_simbolismo\" = '' "
            "THEN 'Não declarado' ELSE m.\"potencia_simbolismo\" END as potencia, "
            "COUNT(*) as total "
            "FROM member m "
            "JOIN tenant t ON m.\"tenantId\" = t.id "
            "WHERE t.code = %s AND m.situacao = 'ATIVO' "
            "GROUP BY potencia ORDER BY total DESC",
            (tenant_code,),
        )
        return [{'name': row[0], 'total': row[1]} for row in cur.fetchall()]
    finally:
        conn.close()


def membros_por_tempo_maconaria(tenant_code='GPRB'):
    """Retorna a contagem de membros ativos por tempo de iniciação na maçonaria.

    Faixas: até 10 anos, até 20 anos, até 30 anos, mais de 40 anos.
    Exclui membros sem dataIniciacao.
    Retorna lista de dicts:
        [{'label': 'Até 10 anos', 'total': 5}, ...]
    """
    from datetime import date

    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT m."dataIniciacao" '
            'FROM member m '
            'JOIN tenant t ON m."tenantId" = t.id '
            "WHERE t.code = %s AND m.situacao = 'ATIVO' "
            'AND m."dataIniciacao" IS NOT NULL',
            (tenant_code,),
        )
        hoje = date.today()
        faixas = {'Até 10 anos': 0, 'Até 20 anos': 0, 'Até 30 anos': 0, 'Mais de 40 anos': 0}
        for row in cur.fetchall():
            di = row[0]
            if hasattr(di, 'date'):
                di = di.date()
            anos = hoje.year - di.year - ((hoje.month, hoje.day) < (di.month, di.day))
            if anos <= 10:
                faixas['Até 10 anos'] += 1
            elif anos <= 20:
                faixas['Até 20 anos'] += 1
            elif anos <= 30:
                faixas['Até 30 anos'] += 1
            else:
                faixas['Mais de 40 anos'] += 1
        return [{'label': k, 'total': v} for k, v in faixas.items()]
    finally:
        conn.close()


def autenticar_usuario(identifier, senha, tenant_code='GPRB'):
    """Autentica um usuario pelo loginIdentifier (telefone/email) contra o banco GPRB.

    Retorna dict com dados do usuario ou None se falhar:
        {'id': ..., 'name': ..., 'email': ..., 'role': ..., 'tenant_id': ...}
    """
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT u.id, u."name", u.email, u."loginIdentifier", '
            'u."passwordHash", u.role, u."tenantId", u.status '
            'FROM "user" u '
            'JOIN tenant t ON u."tenantId" = t.id '
            'WHERE (u."loginIdentifier" = %s OR u.email = %s) '
            'AND t.code = %s',
            (identifier, identifier, tenant_code),
        )
        row = cur.fetchone()
        if row is None:
            return None

        user_id, name, email, login_id, password_hash, role, tenant_id, status = row
        if status != 'ACTIVE':
            return None
        if not password_hash:
            return None

        # Verifica senha bcrypt
        if not bcrypt.checkpw(senha.encode('utf-8'), password_hash.encode('utf-8')):
            return None

        # Atualiza lastLoginAt
        cur.execute(
            'UPDATE "user" SET "lastLoginAt" = NOW() WHERE id = %s',
            (user_id,),
        )
        conn.commit()

        return {
            'id': user_id,
            'name': name,
            'email': email,
            'login_identifier': login_id,
            'role': role,
            'tenant_id': tenant_id,
        }
    finally:
        conn.close()


def existe_usuario(identifier, tenant_code='GPRB'):
    """Verifica se um loginIdentifier/email existe no banco GPRB (independente de senha).

    Usado pelo login para saber se o identificador pertence ao GPRB — nesse caso
    a palavra final sobre a senha é sempre do banco GPRB (nunca do espelho local).
    """
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT 1 FROM "user" u '
            'JOIN tenant t ON u."tenantId" = t.id '
            'WHERE (u."loginIdentifier" = %s OR u.email = %s) '
            'AND t.code = %s AND u."deletedAt" IS NULL '
            'LIMIT 1',
            (identifier, identifier, tenant_code),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def ranking_lojas(tenant_code='GPRB', limite=10):
    """Retorna ranking das lojas com mais membros ativos.

    Retorna lista de dicts ordenada por total de membros (descendente):
        [{'nome': 'Loja X', 'total': 85, 'mx': 30, 'en': 28, 'cbcs': 27, 'rank': 1}, ...]
    """
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COALESCE(l.\"nomeFantasia\", l.\"lojaMX\", 'Loja ' || l.numero::text), "
            "COUNT(m.id) as total, "
            "SUM(CASE WHEN c.abbreviation = 'MX' THEN 1 ELSE 0 END) as mx, "
            "SUM(CASE WHEN c.abbreviation = 'EN' THEN 1 ELSE 0 END) as en, "
            "SUM(CASE WHEN c.abbreviation = 'CBCS' THEN 1 ELSE 0 END) as cbcs "
            "FROM loja l "
            "JOIN member m ON m.\"lojaId\" = l.id AND m.situacao = 'ATIVO' "
            "LEFT JOIN class c ON m.class_id = c.id "
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
                'mx': r[2] or 0,
                'en': r[3] or 0,
                'cbcs': r[4] or 0,
            })
        return resultado
    finally:
        conn.close()


def ranking_lojas_mx(tenant_code='GPRB', limite=10, anos=None):
    """Retorna ranking das lojas com mais membros MX.

    Se anos for informado, filtra por apresentacao_mx nos últimos N anos.
    Caso contrário, retorna todas as lojas MX ativas.
    Retorna lista de dicts:
        [{'nome': 'Loja X', 'total_mx': 32, 'primeira_mx': '10/01/2024', 'ultima_mx': '15/06/2026', 'rank': 1}, ...]
    """
    from datetime import date, timedelta
    conn = connect()
    try:
        cur = conn.cursor()
        params = [tenant_code]
        where_extra = ''
        if anos is not None:
            data_inicio = date.today() - timedelta(days=anos * 365)
            where_extra = ' AND m.\"apresentacao_mx\" >= %s'
            params.append(data_inicio)
        params.append(limite)
        cur.execute(
            "SELECT COALESCE(l.\"nomeFantasia\", l.\"lojaMX\", 'Loja ' || l.numero::text), "
            "COUNT(m.id) as total_mx, "
            "MIN(m.\"apresentacao_mx\")::date as primeira_mx, "
            "MAX(m.\"apresentacao_mx\")::date as ultima_mx "
            "FROM loja l "
            "JOIN member m ON m.\"lojaId\" = l.id AND m.situacao = 'ATIVO' "
            "JOIN class c ON m.class_id = c.id AND c.abbreviation = 'MX' "
            "JOIN tenant t ON l.\"tenantId\" = t.id "
            "WHERE t.code = %s" + where_extra + " "
            "GROUP BY l.id, l.\"nomeFantasia\", l.\"lojaMX\", l.numero "
            "ORDER BY total_mx DESC "
            "LIMIT %s",
            tuple(params),
        )
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


def agendamento_lojas(tenant_code='GPRB'):
    """Retorna agendamento de sessões por loja no ano corrente.

    Retorna lista de dicts:
        [{'loja': 'Loja X', 'realizadas': 5, 'agendadas': 7, 'cor': 'verde'}, ...]
    cor: 'vermelho' (0 sessões ou <4), 'amarelo' (tem mas <4 realizadas), 'verde' (>=4 realizadas)
    """
    from datetime import date
    ano_atual = date.today().year
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COALESCE(l.\"nomeFantasia\", l.\"lojaMX\", 'Loja ' || l.numero::text), "
            "SUM(CASE WHEN m.\"dataSessao\"::date <= CURRENT_DATE THEN 1 ELSE 0 END) as realizadas, "
            "SUM(CASE WHEN m.\"dataSessao\"::date > CURRENT_DATE THEN 1 ELSE 0 END) as agendadas "
            "FROM loja l "
            "LEFT JOIN meeting m ON m.\"lojaId\" = l.id AND EXTRACT(YEAR FROM m.\"dataSessao\") = %s "
            "JOIN tenant t ON l.\"tenantId\" = t.id "
            "WHERE t.code = %s "
            "GROUP BY l.id, l.\"nomeFantasia\", l.\"lojaMX\", l.numero "
            "ORDER BY realizadas DESC, l.\"nomeFantasia\"",
            (ano_atual, tenant_code),
        )
        resultado = []
        for r in cur.fetchall():
            realizadas = r[1] or 0
            agendadas = r[2] or 0
            if realizadas == 0 and agendadas == 0:
                cor = 'vermelho'
            elif realizadas < 4:
                cor = 'amarelo'
            else:
                cor = 'verde'
            resultado.append({
                'loja': r[0],
                'realizadas': realizadas,
                'agendadas': agendadas,
                'cor': cor,
            })
        return resultado
    finally:
        conn.close()


def proximas_sessoes(tenant_code='GPRB', limite=6):
    """Retorna as proximas sessoes agendadas nas lojas (dataSessao >= hoje).

    Le da agenda de sessoes da aplicacao (tabela meeting) e retorna lista de
    dicts ordenada por data (ascendente), limitada a `limite`:
        [{'id': ..., 'loja': 'Loja X', 'dia': '20', 'mes': 'Set',
          'data_fmt': '20/09/2026', 'tipo': 'Ritualística'}, ...]
    """
    from datetime import date

    MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
             'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
    hoje = date.today()
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT m.id, m.\"dataSessao\"::date, "
            "COALESCE(l.\"nomeFantasia\", l.\"lojaMX\", 'Loja ' || l.numero::text), "
            "m.tipo, m.titulo "
            "FROM meeting m "
            "JOIN loja l ON m.\"lojaId\" = l.id "
            "JOIN tenant t ON l.\"tenantId\" = t.id "
            "WHERE t.code = %s AND m.\"dataSessao\"::date >= %s "
            "ORDER BY m.\"dataSessao\" ASC, 3 ASC "
            "LIMIT %s",
            (tenant_code, hoje, limite),
        )
        resultado = []
        for r in cur.fetchall():
            d = r[1]
            if d is None:
                continue
            # Descricao curta da sessao (tipo ou titulo) — descarta valores
            # gravados com charset quebrado (U+FFFD) no banco legado.
            desc = ''
            for campo in (r[3], r[4]):
                cand = (campo or '').strip().replace('\ufffd', '').strip()
                if cand:
                    desc = cand
                    break
            resultado.append({
                'id': r[0],
                'loja': r[2] or '',
                'dia': f'{d.day:02d}',
                'mes': MESES[d.month - 1],
                'data_fmt': d.strftime('%d/%m/%Y'),
                'tipo': desc,
            })
        return resultado
    finally:
        conn.close()


def _months_between(start, end=None):
    """Meses completos entre duas datas."""
    from datetime import date
    if end is None:
        end = date.today()
    if start is None:
        return 0
    if isinstance(start, str):
        try:
            start = date.fromisoformat(str(start)[:10])
        except Exception as e:
            logger.warning('Erro ao converter data "%s" em _months_between: %s', start, e)
            return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)


def _years_between(start, end=None):
    """Anos completos entre duas datas."""
    from datetime import date
    if end is None:
        end = date.today()
    if start is None:
        return 0
    if isinstance(start, str):
        try:
            start = date.fromisoformat(str(start)[:10])
        except Exception as e:
            logger.warning('Erro ao converter data "%s" em _years_between: %s', start, e)
            return 0
    years = end.year - start.year
    if (end.month, end.day) < (start.month, start.day):
        years -= 1
    return max(years, 0)


def ranking_dados(tenant_code='GPRB', classe='MX', loja_id=None, prefeitura_id=None,
                  data_inicio=None, data_fim=None):
    """Retorna dados para o ranking de presença.

    Retorna dict com:
        meetings: [{id, data, tipo, titulo}]
        members: [{id, nome, recepcao, data_nascimento, classe_abbr, classe_nome, anuidade_ok}]
        attendances: {memberId_meetingId: status}
        memberStats: [{memberId, totalPresent, totalRecorded, totalAbsent, percentage}]

    `classe` pode ser None para retornar membros de todas as classes (KPIs
    estáticos do ranking). `loja_id`/`prefeitura_id` restringem as sessões
    e membros ao filtro escolhido.
    """
    from datetime import date, timedelta
    import re

    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM tenant WHERE code = %s", (tenant_code,))
        tid = cur.fetchone()[0]

        # Período padrão: últimos 24 meses
        if data_inicio is None:
            data_inicio = date(date.today().year - 2, 1, 1)
        if data_fim is None:
            data_fim = date.today()

        # Buscar sessões realizadas no período
        params_meet = [tid, data_inicio, data_fim]
        query_meet = (
            'SELECT m.id, m."dataSessao"::date, m.tipo, m.titulo '
            'FROM meeting m '
            'WHERE m."tenantId" = %s '
            'AND m."dataSessao"::date >= %s AND m."dataSessao"::date <= %s '
            'AND m."dataSessao"::date <= CURRENT_DATE '
        )
        if loja_id:
            query_meet += 'AND m."lojaId" = %s '
            params_meet.append(loja_id)
        if prefeitura_id:
            query_meet += ('AND m."lojaId" IN '
                           '(SELECT l2.id FROM loja l2 WHERE l2."prefeituraId" = %s) ')
            params_meet.append(prefeitura_id)
        query_meet += 'ORDER BY m."dataSessao" ASC'
        cur.execute(query_meet, params_meet)
        meetings = [{'id': r[0], 'data': r[1].isoformat() if r[1] else '',
                     'tipo': r[2] or '', 'titulo': r[3] or ''}
                    for r in cur.fetchall()]
        meeting_ids = [m['id'] for m in meetings]
        total_meetings = len(meetings)

        # Ano de referência da anuidade
        from datetime import date as _date
        _hoje = _date.today()
        _ano_ref = _hoje.year + 1 if _hoje.month >= 10 else _hoje.year

        # Buscar membros ativos da classe (com verificação de anuidade)
        class_abbr = classe.upper().strip() if classe else None
        params_mem = [_ano_ref, tid, 'ATIVO']
        query_mem = (
            'SELECT m.id, m."nomeCompleto", '
            'COALESCE(m."apresentacao_mx", m."apresentacao_ec"), '
            'm."dataNascimento", c.abbreviation, c.name, '
            'EXISTS('
            '  SELECT 1 FROM payment_status ps '
            '  JOIN payment_period pp ON ps."periodId" = pp.id '
            '  WHERE ps."memberId" = m.id AND pp.type = \'ANNUAL\' '
            '  AND pp.year = %s AND ps.status = \'PAID\''
            ') as anuidade_ok, '
            'COALESCE(l."nomeFantasia", \'Loja \' || l.numero::text) as loja_nome, '
            'p.sigla as prefeitura_sigla '
            'FROM member m '
            'JOIN class c ON m.class_id = c.id '
            'LEFT JOIN loja l ON m."lojaId" = l.id '
            'LEFT JOIN prefeitura p ON l."prefeituraId" = p.id '
            'WHERE m."tenantId" = %s AND m.situacao = %s '
        )
        if class_abbr:
            query_mem += 'AND c.abbreviation = %s '
            params_mem.append(class_abbr)
        if loja_id:
            query_mem += 'AND m."lojaId" = %s '
            params_mem.append(loja_id)
        if prefeitura_id:
            query_mem += 'AND l."prefeituraId" = %s '
            params_mem.append(prefeitura_id)
        query_mem += 'ORDER BY m."nomeCompleto" ASC'
        cur.execute(query_mem, params_mem)
        members = []
        for r in cur.fetchall():
            recepcao = r[2]
            if recepcao and hasattr(recepcao, 'date'):
                recepcao = recepcao.date()
            members.append({
                'id': r[0], 'nome': r[1] or '',
                'recepcao': recepcao.isoformat() if recepcao else '',
                'data_nascimento': r[3].isoformat() if r[3] else '',
                'classe_abbr': r[4] or '', 'classe_nome': r[5] or '',
                'anuidade_ok': bool(r[6]),
                'loja_nome': r[7] or '',
                'prefeitura_sigla': r[8] or '',
            })
        member_ids = [m['id'] for m in members]

        # Buscar presenças
        attendances = {}
        if meeting_ids and member_ids:
            # Query em lotes para evitar many params
            for i in range(0, len(member_ids), 50):
                batch = member_ids[i:i+50]
                placeholders = ','.join(['%s'] * len(batch))
                cur.execute(
                    f'SELECT "memberId", "meetingId", status '
                    f'FROM attendance '
                    f'WHERE "tenantId" = %s '
                    f'AND "memberId" IN ({placeholders})',
                    [tid] + batch,
                )
                for r in cur.fetchall():
                    attendances[f'{r[0]}_{r[1]}'] = r[2]

        # Calcular estatísticas por membro
        member_stats = []
        for m in members:
            total_present = sum(
                1 for mid in meeting_ids
                if attendances.get(f'{m["id"]}_{mid}') == 'PRESENTE'
            )
            total_absent = sum(
                1 for mid in meeting_ids
                if attendances.get(f'{m["id"]}_{mid}') == 'FALTA'
            )
            percentage = round((total_present / total_meetings * 100)) if total_meetings > 0 else 0
            member_stats.append({
                'memberId': m['id'],
                'totalPresent': total_present,
                'totalAbsent': total_absent,
                'totalRecorded': total_meetings,
                'percentage': percentage,
            })

        return {
            'meetings': meetings,
            'members': members,
            'attendances': attendances,
            'memberStats': member_stats,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Usuários do sistema (tabela "user" — gestão na tela /equipe/)
# ---------------------------------------------------------------------------

ROLE_LABELS_GPRB = {
    'SYS_ADMIN': 'Administrador do Sistema',
    'ADMIN_LOJA': 'Administrador da Loja',
    'GRANDE_PRIOR': 'Grão Prior',
    'GRANDE_TESOUREIRO': 'Grande Tesoureiro',
    'GRANDE_CHANCELER': 'Grande Chanceler',
    'GRANDE_SECRETARIO': 'Grande Secretário',
    'PREFEITO': 'Prefeito',
    'DEPUTADO_MESTRE': 'Deputado Mestre',
    'SECRETARIA': 'Secretaria',
    'TESOURARIA': 'Tesouraria',
    'MEMBER': 'Membro',
    'OPERADOR': 'Operador',
}

STATUS_LABELS_GPRB = {
    'ACTIVE': 'Ativo',
    'INACTIVE': 'Inativo',
    'PENDING': 'Pendente',
}


def coluna_existe(cur, tabela, coluna):
    """True quando a coluna existe na tabela do GPRB (schema compartilhado varia)."""
    cur.execute(
        'SELECT 1 FROM information_schema.columns '
        'WHERE table_name = %s AND column_name = %s LIMIT 1',
        (tabela, coluna),
    )
    return cur.fetchone() is not None


def _tenant_id_por_codigo(cur, tenant_code='GPRB'):
    cur.execute('SELECT id FROM tenant WHERE code = %s', (tenant_code,))
    row = cur.fetchone()
    return row[0] if row else None


def label_role_gprb(role):
    """Rótulo legível de um perfil GPRB."""
    if not role:
        return '—'
    return ROLE_LABELS_GPRB.get(role, role.replace('_', ' ').title())


def listar_usuarios_sistema(
    tenant_code='GPRB', *, q='', loja_id='', perfil='', status='',
):
    """Lista usuários do sistema GPRB com filtros opcionais."""
    conn = connect()
    try:
        cur = conn.cursor()
        sql = (
            'SELECT u.id, u.name, u.email, u.role, u.status, u."lastLoginAt", '
            'COALESCE(l."nomeFantasia", l."lojaMX"), l.numero, u."loginIdentifier" '
            'FROM "user" u '
            'JOIN tenant t ON u."tenantId" = t.id '
            'LEFT JOIN loja l ON u."lojaId" = l.id '
            'WHERE t.code = %s AND u."deletedAt" IS NULL'
        )
        params = [tenant_code]
        if q:
            sql += ' AND (u.name ILIKE %s OR u.email ILIKE %s OR u."loginIdentifier" ILIKE %s)'
            like = f'%{q}%'
            params.extend([like, like, like])
        if loja_id:
            sql += ' AND u."lojaId" = %s'
            params.append(loja_id)
        if perfil:
            sql += ' AND u.role = %s'
            params.append(perfil)
        if status:
            sql += ' AND u.status = %s'
            params.append(status.upper())
        sql += ' ORDER BY u.name NULLS LAST, u.email'
        cur.execute(sql, params)
        resultado = []
        for r in cur.fetchall():
            loja_nome = r[6] or ''
            loja_num = r[7]
            resultado.append({
                'id': r[0],
                'gprb': True,
                'nome': r[1] or r[2] or '—',
                'email': r[2] or '—',
                'loja_nome': loja_nome,
                'loja_numero': loja_num if loja_num is not None else '',
                'loja_display': loja_nome or '—',
                'papel': r[3],
                'papel_label': label_role_gprb(r[3]),
                'ultimo_acesso': r[5],
                'status_code': r[4],
                'status_label': STATUS_LABELS_GPRB.get(r[4], r[4] or '—'),
                'pendente': False,
                'pode_reenviar': False,
                'celular': r[8] or '',
            })
        return resultado
    finally:
        conn.close()


def opcoes_lojas_usuario(tenant_code='GPRB'):
    """Lojas do tenant para filtro/cadastro de usuários."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT l.id, COALESCE(l."nomeFantasia", l."lojaMX"), l.numero '
            'FROM loja l JOIN tenant t ON l."tenantId" = t.id '
            'WHERE t.code = %s ORDER BY l."lojaMX" NULLS LAST, l.numero NULLS LAST',
            (tenant_code,),
        )
        return [
            {'id': r[0], 'nome': r[1] or 'Loja', 'numero': r[2]}
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


def opcoes_prefeituras_usuario(tenant_code='GPRB'):
    """Prefeituras do tenant para cadastro de usuários."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT p.id, p.nome FROM prefeitura p '
            'JOIN tenant t ON p."tenantId" = t.id '
            'WHERE t.code = %s ORDER BY p.nome',
            (tenant_code,),
        )
        return [{'id': r[0], 'nome': r[1]} for r in cur.fetchall()]
    finally:
        conn.close()


def opcoes_perfis_usuario(tenant_code='GPRB'):
    """Perfis distintos cadastrados no tenant (para filtro)."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT DISTINCT u.role FROM "user" u '
            'JOIN tenant t ON u."tenantId" = t.id '
            'WHERE t.code = %s AND u."deletedAt" IS NULL AND u.role IS NOT NULL '
            'ORDER BY u.role',
            (tenant_code,),
        )
        return [
            {'key': r[0], 'label': label_role_gprb(r[0])}
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


def obter_usuario_sistema(user_id, tenant_code='GPRB'):
    """Detalhe de um usuário GPRB pelo id (UUID)."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            'SELECT u.id, u.name, u.email, u.role, u.status, u."lastLoginAt", '
            'u."loginIdentifier", u."prefeituraId", u."lojaId", u."createdAt", '
            'COALESCE(l."nomeFantasia", l."lojaMX"), l.numero, p.nome '
            'FROM "user" u '
            'JOIN tenant t ON u."tenantId" = t.id '
            'LEFT JOIN loja l ON u."lojaId" = l.id '
            'LEFT JOIN prefeitura p ON u."prefeituraId" = p.id '
            'WHERE u.id = %s AND t.code = %s AND u."deletedAt" IS NULL',
            (user_id, tenant_code),
        )
        r = cur.fetchone()
        if r is None:
            return None
        return {
            'id': r[0], 'gprb': True, 'nome': r[1] or r[2], 'email': r[2],
            'papel': r[3], 'papel_label': label_role_gprb(r[3]),
            'status_code': r[4], 'status_label': STATUS_LABELS_GPRB.get(r[4], r[4]),
            'ultimo_acesso': r[5], 'celular': r[6] or '', 'prefeitura_id': r[7] or '',
            'loja_id': r[8] or '', 'criado_em': r[9],
            'loja_nome': r[10] or '', 'loja_numero': r[11],
            'prefeitura_nome': r[12] or '—',
        }
    finally:
        conn.close()


def atualizar_usuario_sistema(user_id, *, nome, email, celular, role, prefeitura_id=''):
    """Atualiza campos básicos de um usuário GPRB."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            'UPDATE "user" SET name = %s, email = %s, "loginIdentifier" = %s, '
            'role = %s, "prefeituraId" = %s, "updatedAt" = NOW() '
            'WHERE id = %s AND "deletedAt" IS NULL',
            (nome, email, celular or email, role, prefeitura_id or None, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def excluir_usuario_sistema(user_id):
    """Soft-delete de usuário GPRB."""
    conn = connect()
    try:
        cur = conn.cursor()
        cur.execute(
            'UPDATE "user" SET "deletedAt" = NOW(), "updatedAt" = NOW() '
            'WHERE id = %s AND "deletedAt" IS NULL',
            (user_id,),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
