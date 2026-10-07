"""Consultas de membros e lojas no banco GPRB."""

from datetime import date

from core.gprb.connection import connect


def membros_por_situacao(tenant_code='GPRB', apenas_ativos=True, ano=None):
    """Retorna a contagem de membros agrupados por situacao (ATIVO/INATIVO).

    Substitui membros_por_classe — classes (MX/EN/CBCS) nao se aplicam mais ao
    projeto. Retorna lista de dicts:
        [{'name': 'ATIVO', 'total': 143}, ...]
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
        sql = (
            "SELECT m.situacao as name, COUNT(m.id) as total "  # nosec B608 - fragmentos literais; valores parametrizados
            "FROM member m "
            "JOIN tenant t ON m.\"tenantId\" = t.id "
            "WHERE " + where + " "
            "GROUP BY m.situacao "
            "ORDER BY total DESC"
        )
        cur.execute(sql, params)  # nosec B608 - apenas estrutura interna; valores parametrizados
        return [
            {'name': row[0], 'total': row[1]}
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
        sql = (
            "SELECT COUNT(m.id) "  # nosec B608 - fragmentos literais; valores parametrizados
            "FROM member m "
            "JOIN tenant t ON m.\"tenantId\" = t.id "
            "WHERE " + where
        )
        cur.execute(sql, params)  # nosec B608 - apenas estrutura interna; valores parametrizados
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
        ano = date.today().year
    return total_membros(tenant_code=tenant_code, apenas_ativos=True, ano=ano)


def anuidade_ano_referencia():
    """Ano de referência da anuidade: mês ≤ 9 → ano corrente; mês ≥ 10 → ano corrente + 1."""
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


def agendamento_lojas(tenant_code='GPRB'):
    """Retorna agendamento de sessões por loja no ano corrente.

    Retorna lista de dicts:
        [{'loja': 'Loja X', 'realizadas': 5, 'agendadas': 7, 'cor': 'verde'}, ...]
    cor: 'vermelho' (0 sessões ou <4), 'amarelo' (tem mas <4 realizadas), 'verde' (>=4 realizadas)
    """
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
