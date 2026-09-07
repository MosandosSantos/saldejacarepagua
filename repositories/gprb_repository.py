"""Repository para o banco de dados GPRB (PostgreSQL externo).

Centraliza todas as queries SQL que antes estavam espalhadas em views.
Cada metodo encapsula uma operacao: abre conexao, executa, fecha.
"""
import uuid
from contextlib import contextmanager

from core.gprb import coluna_existe, connect


@contextmanager
def gprb_cursor():
    """Context manager que abre e fecha conexao GPRB automaticamente."""
    conn = connect()
    try:
        yield conn.cursor()
    finally:
        conn.close()


_COLUNAS_MEMBER_PERMITIDAS = frozenset({
    'rito', 'potencia_simbolismo', 'cargo', 'tipoAdmissao',
    'escolaridade', 'estadoCivil', 'enderecoCidade', 'enderecoBairro',
    'enderecoEstado', 'nomeCompleto', 'email', 'celular', 'cpf',
    'dataNascimento', 'dataAdmissao', 'dataElevacao', 'dataInativacao',
    'classe', 'loja', 'situacao', 'sexo', 'naturalidade', 'nacionalidade',
    'nomePai', 'nomeMae', 'conjuge', 'formacao',
    'instituicao', 'empresa', 'cargoEmpresa', 'telefoneEmpresa',
    'enderecoRua', 'enderecoNumero', 'enderecoComplemento', 'enderecoCEP',
    'observacao', 'foto', 'tenant', 'potencia', 'situacaoEspecial',
})


def _obter_tenant_gprb():
    """Retorna o id do tenant GPRB."""
    with gprb_cursor() as cur:
        cur.execute("SELECT id FROM tenant WHERE code = 'GPRB'")
        return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Membros
# ---------------------------------------------------------------------------

def buscar_membro(member_id):
    """Busca um membro pelo ID — todos os campos da ficha."""
    with gprb_cursor() as cur:
        cur.execute('''
        SELECT m.id, m."nomeCompleto", m.email, m.celular, m.cpf,
           m."enderecoLogradouro", m."enderecoNumero", m."enderecoComplemento",
           m."enderecoBairro", m."enderecoCidade", m."enderecoUf", m."enderecoCep",
           m.situacao, m."dataNascimento", m."dataAdmissao",
           m."apresentacao_mx", m."apresentacao_ec", m."armadura_cbcs",
           m.rito, m."numeroFiliado", m."tipoAdmissao", m.escolaridade,
           m.nacionalidade, m."naturalCidade", m."estadoCivil", m.pai, m.mae,
           m."identidadeNumero", m."orgaoEmissor", m."dataEmissao",
           m."telefoneUrgencia", m."dataPassagem", m."dataElevacao", m."dataInstalacao",
           m."dataIniciacao", m."potencia_simbolismo", m.cargo,
           m."condicao_mensalidade", m."lojaId", m.class_id,
           m."createdAt", m."updatedAt",
           c.name as classe, c.abbreviation as classe_abbr,
           l."nomeFantasia", l.numero as loja_numero,
           p.nome as prefeitura_nome, p.sigla as prefeitura_sigla
        FROM member m
        LEFT JOIN class c ON m.class_id = c.id
        LEFT JOIN loja l ON m."lojaId" = l.id
        LEFT JOIN prefeitura p ON l."prefeituraId" = p.id
        WHERE m.id = %s
        ''', (member_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return {
            'id': row[0], 'nome': row[1] or '', 'email': row[2] or '',
            'celular': row[3] or '', 'cpf': row[4] or '',
            'endereco': row[5] or '', 'numero': row[6] or '',
            'complemento': row[7] or '', 'bairro': row[8] or '',
            'cidade': row[9] or '', 'uf': row[10] or '', 'cep': row[11] or '',
            'situacao': row[12] or '', 'data_nascimento': row[13],
            'data_admissao': row[14],
            'apresentacao_mx': row[15], 'apresentacao_ec': row[16],
            'armadura_cbcs': row[17],
            'rito': row[18] or '', 'cadastro_maconico': row[19] or '',
            'tipo_admissao': row[20] or '', 'escolaridade': row[21] or '',
            'nacionalidade': row[22] or '', 'naturalidade': row[23] or '',
            'estado_civil': row[24] or '', 'pai': row[25] or '', 'mae': row[26] or '',
            'identidade': row[27] or '', 'orgao_emissor': row[28] or '',
            'data_emissao': row[29],
            'telefone_urgencia': row[30] or '',
            'data_passagem': row[31], 'data_elevacao': row[32],
            'data_instalacao': row[33],
            'data_iniciacao': row[34],
            'potencia': row[35] or '', 'cargo': row[36] or '',
            'condicao': row[37] or '',
            'loja_id': row[38] or '', 'class_id': str(row[39]) if row[39] else '',
            'criado_em': row[40], 'atualizado_em': row[41],
            'classe': row[42] or '', 'classe_abbr': row[43] or '',
            'loja': row[44] or (f'Loja {row[45]}' if row[45] else '—'),
            'prefeitura': row[46] or row[47] or '—',
        }


def atualizar_membro(member_id, dados):
    """Atualiza um membro no banco GPRB. `dados` e um dict com as colunas."""
    with gprb_cursor() as cur:
        colunas = ', '.join(f'"{k}" = %s' for k in dados)
        valores = list(dados.values()) + [member_id]
        cur.execute(f'UPDATE member SET {colunas}, "updatedAt" = NOW() WHERE id = %s', valores)  # nosec B608
        cur.connection.commit()


def inativar_membro(member_id):
    """Marca membro como INATIVO."""
    with gprb_cursor() as cur:
        cur.execute(
            'UPDATE member SET situacao = %s, "updatedAt" = NOW() WHERE id = %s',
            ('INATIVO', member_id),
        )
        cur.connection.commit()


def excluir_membro(member_id):
    """Exclui um membro do banco GPRB."""
    with gprb_cursor() as cur:
        cur.execute('DELETE FROM member WHERE id = %s', (member_id,))
        cur.connection.commit()


def listar_membros_filtros():
    """Retorna opcoes para os filtros da listagem de membros."""
    tid = _obter_tenant_gprb()
    with gprb_cursor() as cur:
        cur.execute(
            'SELECT id, nome FROM prefeitura WHERE "tenantId" = %s ORDER BY nome',
            (tid,),
        )
        prefeituras = [{'id': r[0], 'nome': r[1]} for r in cur.fetchall()]

        cur.execute(
            'SELECT id, COALESCE("nomeFantasia", "lojaMX", \'Loja \' || numero::text) '
            'FROM loja WHERE "tenantId" = %s ORDER BY 2',
            (tid,),
        )
        lojas = [{'id': r[0], 'nome': r[1]} for r in cur.fetchall()]

        cur.execute(
            "SELECT DISTINCT \"enderecoUf\" FROM member "
            "WHERE \"tenantId\" = %s AND \"enderecoUf\" IS NOT NULL "
            "AND \"enderecoUf\" <> '' ORDER BY 1",
            (tid,),
        )
        ufs = [r[0] for r in cur.fetchall()]

        cur.execute(
            "SELECT DISTINCT REPLACE(COALESCE(\"enderecoCidade\", ''), chr(65533), '') "
            "FROM member "
            "WHERE \"tenantId\" = %s "
            "AND REPLACE(COALESCE(\"enderecoCidade\", ''), chr(65533), '') <> '' "
            "ORDER BY 1",
            (tid,),
        )
        cidades = [r[0] for r in cur.fetchall()]

        cur.execute(
            'SELECT DISTINCT c.abbreviation FROM member m '
            'JOIN class c ON m.class_id = c.id '
            'WHERE m."tenantId" = %s AND c.abbreviation IS NOT NULL '
            "AND c.abbreviation <> '' ORDER BY 1",
            (tid,),
        )
        graus = [r[0] for r in cur.fetchall()]

        return {
            'prefeituras': prefeituras,
            'lojas': lojas,
            'ufs': ufs,
            'cidades': cidades,
            'graus': graus,
        }


def listar_membros(filtros):
    """Lista membros com filtros acumulativos.

    `filtros` e um dict com chaves: termo, situacao, prefeitura_id, loja_id,
    uf, cidade, grau.
    Retorna lista de tuples (row format) com 16 colunas.
    """
    where = 'WHERE t.code = %s'
    params = ['GPRB']
    if filtros.get('termo'):
        where += ' AND (m."nomeCompleto" ILIKE %s OR m.email ILIKE %s OR m.celular ILIKE %s)'
        params.extend([f'%{filtros["termo"]}%'] * 3)
    if filtros.get('situacao') == 'ATIVO':
        where += ' AND m.situacao = %s'
        params.append('ATIVO')
    elif filtros.get('situacao') == 'INATIVO':
        where += " AND m.situacao IS DISTINCT FROM 'ATIVO'"
    if filtros.get('prefeitura_id'):
        where += ' AND p.id = %s'
        params.append(filtros['prefeitura_id'])
    if filtros.get('loja_id'):
        where += ' AND m."lojaId" = %s'
        params.append(filtros['loja_id'])
    if filtros.get('uf'):
        where += ' AND m."enderecoUf" = %s'
        params.append(filtros['uf'])
    if filtros.get('cidade'):
        where += " AND REPLACE(COALESCE(m.\"enderecoCidade\", ''), chr(65533), '') = %s"
        params.append(filtros['cidade'])
    if filtros.get('grau'):
        where += ' AND c.abbreviation = %s'
        params.append(filtros['grau'])

    with gprb_cursor() as cur:
        cur.execute(
            f'''
        SELECT m.id, m."nomeCompleto", m.email, m.celular, m.cpf,
           m."enderecoCidade", m."enderecoUf", m.situacao,
           c.name as classe, c.abbreviation as classe_abbr,
           l."nomeFantasia", l.numero as loja_numero,
           p.nome as prefeitura_nome, p.sigla as prefeitura_sigla,
           m."createdAt",
           (SELECT MAX(pp.year) FROM payment_status ps2
            JOIN payment_period pp ON ps2."periodId" = pp.id
            WHERE ps2."memberId" = m.id AND pp.type = 'ANNUAL'
              AND ps2.status = 'PAID') as ultima_anuidade
        FROM member m
        JOIN tenant t ON m."tenantId" = t.id
        LEFT JOIN class c ON m.class_id = c.id
        LEFT JOIN loja l ON m."lojaId" = l.id
        LEFT JOIN prefeitura p ON l."prefeituraId" = p.id
        {where}
        ORDER BY m."createdAt" DESC
        ''', params)
        return cur.fetchall()


# ---------------------------------------------------------------------------
# Lojas
# ---------------------------------------------------------------------------

def listar_lojas(termo=''):
    """Lista lojas com contagem de membros. Retorna (lojas_list, total)."""
    tid = _obter_tenant_gprb()
    where = 'WHERE l."tenantId" = %s'
    params = [tid]
    if termo:
        where += ' AND (l."nomeFantasia" ILIKE %s OR l.numero::text ILIKE %s)'
        params.extend([f'%{termo}%', f'%{termo}%'])

    with gprb_cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM loja l {where}', params)  # nosec B608
        total = cur.fetchone()[0]

        cur.execute(
            f'''
        SELECT l.id, l."nomeFantasia", l.numero, l.telefone, l.email,
               l."enderecoCidade", l."enderecoUf", l.situacao,
               p.nome as prefeitura_nome, p.regiao,
               COUNT(DISTINCT m.id) as total_membros
        FROM loja l
        LEFT JOIN prefeitura p ON l."prefeituraId" = p.id
        LEFT JOIN member m ON m."lojaId" = l.id
        {where}
        GROUP BY l.id, l."nomeFantasia", l.numero, l.telefone, l.email,
                 l."enderecoCidade", l."enderecoUf", l.situacao,
                 p.nome, p.regiao
        ORDER BY l."nomeFantasia"
        ''', params)
        lojas_list = [
            {
                'id': r[0], 'nome': r[1] or f'Loja {r[2]}', 'numero': r[2],
                'telefone': r[3] or '—', 'email': r[4] or '—',
                'cidade': r[5] or '', 'uf': r[6] or '',
                'situacao': r[7] or '',
                'prefeitura': r[8] or '—', 'regiao': r[9] or '',
                'total_membros': r[10],
            }
            for r in cur.fetchall()
        ]

        deputados = {}
        if coluna_existe(cur, 'loja', 'deputadoMestreId'):
            cur.execute(
                'SELECT l.id, dm."nomeCompleto" FROM loja l '  # nosec B608
                'LEFT JOIN member dm ON dm.id = l."deputadoMestreId" ' + where,
                params,
            )
            deputados = {r[0]: r[1] for r in cur.fetchall()}
        for loja in lojas_list:
            loja['deputado_mestre'] = deputados.get(loja['id']) or '—'

        return lojas_list, total


def buscar_loja(loja_id):
    """Busca detalhe de uma loja. Retorna dict ou None."""
    with gprb_cursor() as cur:
        cur.execute('''
        SELECT l.id, l."nomeFantasia", l.numero, l.telefone, l.email,
           l."enderecoLogradouro", l."enderecoNumero", l."enderecoBairro",
           l."enderecoCidade", l."enderecoUf", l."enderecoCep",
           l.situacao, l."dataFundacao",
           p.nome as prefeitura, p.regiao
        FROM loja l LEFT JOIN prefeitura p ON l."prefeituraId" = p.id
        WHERE l.id = %s
        ''', (loja_id,))
        r = cur.fetchone()
        if r is None:
            return None
        loja = {
            'id': r[0], 'nome': r[1] or f'Loja {r[2]}', 'numero': r[2],
            'telefone': r[3] or '—', 'email': r[4] or '—',
            'endereco': r[5] or '', 'numero_end': r[6] or '', 'bairro': r[7] or '',
            'cidade': r[8] or '', 'uf': r[9] or '', 'cep': r[10] or '',
            'situacao': r[11] or '', 'fundacao': r[12],
            'prefeitura': r[13] or '—', 'regiao': r[14] or '',
        }
        cur.execute('SELECT COUNT(DISTINCT m.id) FROM member m WHERE m."lojaId" = %s', (loja_id,))
        loja['total_membros'] = cur.fetchone()[0]

        loja['deputado_mestre_id'] = ''
        loja['deputado_mestre'] = '—'
        if coluna_existe(cur, 'loja', 'deputadoMestreId'):
            cur.execute('SELECT "deputadoMestreId" FROM loja WHERE id = %s', (loja_id,))
            dm_id = cur.fetchone()[0]
            if dm_id:
                loja['deputado_mestre_id'] = dm_id
                cur.execute('SELECT "nomeCompleto" FROM member WHERE id = %s', (dm_id,))
                dm = cur.fetchone()
                loja['deputado_mestre'] = dm[0] if dm else '—'
        return loja


def criar_loja(dados):
    """Insere uma nova loja. `dados` e um dict com os campos."""
    tid = _obter_tenant_gprb()
    with gprb_cursor() as cur:
        cur.execute('''
        INSERT INTO loja (id, "tenantId", "nomeFantasia", numero, telefone, email,
        "prefeituraId", "enderecoCidade", "enderecoUf", situacao,
        "createdAt", "updatedAt")
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'ATIVA', NOW(), NOW())
        ''', (
            str(uuid.uuid4()), tid,
            dados['nome'],
            int(dados['numero']) if dados.get('numero', '').isdigit() else None,
            dados.get('telefone') or None,
            dados.get('email') or None,
            dados.get('prefeitura_id') or None,
            dados.get('cidade') or None,
            dados.get('uf') or None,
        ))
        cur.connection.commit()


def atualizar_loja(loja_id, dados):
    """Atualiza uma loja. `dados` e um dict com os campos."""
    with gprb_cursor() as cur:
        if coluna_existe(cur, 'loja', 'deputadoMestreId'):
            cur.execute('''
            UPDATE loja SET "nomeFantasia" = %s, telefone = %s, email = %s,
                "prefeituraId" = %s, "enderecoCidade" = %s, "enderecoUf" = %s,
                "deputadoMestreId" = %s, "updatedAt" = NOW()
            WHERE id = %s
            ''', (
                dados['nome'],
                dados.get('telefone') or None,
                dados.get('email') or None,
                dados.get('prefeitura_id') or None,
                dados.get('cidade') or None,
                dados.get('uf') or None,
                dados.get('deputado_mestre') or None,
                loja_id,
            ))
        else:
            cur.execute('''
            UPDATE loja SET "nomeFantasia" = %s, telefone = %s, email = %s,
                "prefeituraId" = %s, "enderecoCidade" = %s, "enderecoUf" = %s,
                "updatedAt" = NOW()
            WHERE id = %s
            ''', (
                dados['nome'],
                dados.get('telefone') or None,
                dados.get('email') or None,
                dados.get('prefeitura_id') or None,
                dados.get('cidade') or None,
                dados.get('uf') or None,
                loja_id,
            ))
        cur.connection.commit()


def contar_membros_loja(loja_id):
    """Conta quantos membros pertencem a uma loja."""
    with gprb_cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM member WHERE "lojaId" = %s', (loja_id,))
        return cur.fetchone()[0]


def excluir_loja(loja_id):
    """Exclui uma loja."""
    with gprb_cursor() as cur:
        cur.execute('DELETE FROM loja WHERE id = %s', (loja_id,))
        cur.connection.commit()


def buscar_loja_para_edicao(loja_id):
    """Busca dados de loja para o formulario de edicao."""
    with gprb_cursor() as cur:
        cur.execute('''
        SELECT l.id, l."nomeFantasia", l.numero, l.telefone, l.email,
           l."prefeituraId", l."enderecoCidade", l."enderecoUf", l.situacao
        FROM loja l WHERE l.id = %s
        ''', (loja_id,))
        r = cur.fetchone()
        if r is None:
            return None
        loja = {
            'id': r[0], 'nome': r[1] or '', 'numero': r[2] or '',
            'telefone': r[3] or '', 'email': r[4] or '',
            'prefeitura_id': r[5] or '', 'cidade': r[6] or '', 'uf': r[7] or '',
            'situacao': r[8] or '',
        }
        tid = _obter_tenant_gprb()
        cur.execute('SELECT id, nome, regiao FROM prefeitura WHERE "tenantId" = %s ORDER BY nome', (tid,))
        prefeituras = [{'id': pr[0], 'nome': pr[1], 'regiao': pr[2]} for pr in cur.fetchall()]
        cur.execute(
            'SELECT id, "nomeCompleto" FROM member '
            'WHERE "lojaId" = %s AND situacao = %s ORDER BY "nomeCompleto"',
            (loja_id, 'ATIVO'),
        )
        membros = [{'id': mr[0], 'nome': mr[1]} for mr in cur.fetchall()]

        loja['deputado_mestre_id'] = ''
        if coluna_existe(cur, 'loja', 'deputadoMestreId'):
            cur.execute('SELECT "deputadoMestreId" FROM loja WHERE id = %s', (loja_id,))
            dm_row = cur.fetchone()
            loja['deputado_mestre_id'] = (dm_row[0] or '') if dm_row else ''

        return loja, prefeituras, membros


def listar_lojas_para_select():
    """Lista lojas para selects (usado em formularios de loja nova)."""
    tid = _obter_tenant_gprb()
    with gprb_cursor() as cur:
        cur.execute('SELECT id, nome, regiao FROM prefeitura WHERE "tenantId" = %s ORDER BY nome', (tid,))
        return [{'id': r[0], 'nome': r[1], 'regiao': r[2]} for r in cur.fetchall()]


def listar_membros_loja(loja_id):
    """Lista membros de uma loja (para drill-down JSON)."""
    with gprb_cursor() as cur:
        cur.execute('''
        SELECT m.id, m."nomeCompleto", c.abbreviation, c.name as classe_nome,
           m.situacao, m."dataIniciacao"
        FROM member m
        LEFT JOIN class c ON m.class_id = c.id
        WHERE m."lojaId" = %s
        ORDER BY m.situacao, c.abbreviation, m."nomeCompleto"
        ''', (loja_id,))
        return [
            {
                'id': r[0], 'nome': r[1] or '',
                'classe': r[2] or '—', 'classe_nome': r[3] or '',
                'situacao': r[4] or '',
            }
            for r in cur.fetchall()
        ]


def listar_lojas_por_prefeitura(prefeitura_id):
    """Lista lojas de uma prefeitura (para drill-down JSON)."""
    with gprb_cursor() as cur:
        cur.execute('''
        SELECT l.id, l."nomeFantasia", l."lojaMX", l.numero, l.situacao,
           COUNT(m.id) as membros,
           SUM(CASE WHEN c.abbreviation = 'MX' THEN 1 ELSE 0 END) as mx,
           SUM(CASE WHEN c.abbreviation = 'EN' THEN 1 ELSE 0 END) as en,
           SUM(CASE WHEN c.abbreviation = 'CBCS' THEN 1 ELSE 0 END) as cbcs
        FROM loja l
        LEFT JOIN member m ON m."lojaId" = l.id AND m.situacao = 'ATIVO'
        LEFT JOIN class c ON m.class_id = c.id
        WHERE l."prefeituraId" = %s
        GROUP BY l.id, l."nomeFantasia", l."lojaMX", l.numero, l.situacao
        ORDER BY l."nomeFantasia"
        ''', (prefeitura_id,))
        return [
            {
                'id': r[0], 'nome': r[1] or r[2] or f'Loja #{r[3]}',
                'loja_mx': r[2] or '', 'numero': r[3],
                'situacao': r[4], 'total_membros': r[5],
                'mx': r[6] or 0, 'en': r[7] or 0, 'cbcs': r[8] or 0,
            }
            for r in cur.fetchall()
        ]


# ---------------------------------------------------------------------------
# Prefeituras
# ---------------------------------------------------------------------------

def listar_prefeituras():
    """Lista prefeituras com KPIs. Retorna (prefeituras, total_pf, total_lojas, total_membros)."""
    tid = _obter_tenant_gprb()
    with gprb_cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM prefeitura WHERE "tenantId" = %s', (tid,))
        total_pf = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM loja WHERE "tenantId" = %s', (tid,))
        total_lojas = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM member WHERE "tenantId" = %s', (tid,))
        total_membros = cur.fetchone()[0]

        cur.execute('''
        SELECT p.id, p.nome, p.regiao, p.prefeito, p.telefone,
               COUNT(DISTINCT l.id) as total_lojas,
               COUNT(DISTINCT m.id) as total_membros,
               SUM(CASE WHEN c.abbreviation = 'MX' THEN 1 ELSE 0 END) as mx,
               SUM(CASE WHEN c.abbreviation = 'EN' THEN 1 ELSE 0 END) as en,
               SUM(CASE WHEN c.abbreviation = 'CBCS' THEN 1 ELSE 0 END) as cbcs
        FROM prefeitura p
        LEFT JOIN loja l ON l."prefeituraId" = p.id
        LEFT JOIN member m ON m."lojaId" = l.id AND m.situacao = 'ATIVO'
        LEFT JOIN class c ON m.class_id = c.id
        WHERE p."tenantId" = %s
        GROUP BY p.id, p.nome, p.regiao, p.prefeito, p.telefone
        ORDER BY p.nome
        ''', (tid,))
        prefeituras_list = [
            {
                'id': r[0], 'nome': r[1], 'regiao': r[2],
                'prefeito': r[3] or '—', 'telefone': r[4] or '—',
                'total_lojas': r[5], 'total_membros': r[6],
                'mx': r[7] or 0, 'en': r[8] or 0, 'cbcs': r[9] or 0,
            }
            for r in cur.fetchall()
        ]

        return prefeituras_list, total_pf, total_lojas, total_membros


def criar_prefeitura(dados):
    """Insere uma nova prefeitura."""
    tid = _obter_tenant_gprb()
    with gprb_cursor() as cur:
        if coluna_existe(cur, 'prefeitura', 'email'):
            cur.execute('''
            INSERT INTO prefeitura (id, "tenantId", nome, sigla, regiao, prefeito, telefone, email, status, "createdAt", "updatedAt")
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'ATIVA', NOW(), NOW())
            ''', (
                str(uuid.uuid4()), tid,
                dados['nome'], dados.get('sigla') or None, dados['regiao'],
                dados.get('prefeito') or None, dados.get('telefone') or None,
                dados.get('email') or None,
            ))
        else:
            cur.execute('''
            INSERT INTO prefeitura (id, "tenantId", nome, sigla, regiao, prefeito, telefone, status, "createdAt", "updatedAt")
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'ATIVA', NOW(), NOW())
            ''', (
                str(uuid.uuid4()), tid,
                dados['nome'], dados.get('sigla') or None, dados['regiao'],
                dados.get('prefeito') or None, dados.get('telefone') or None,
            ))
        cur.connection.commit()


def buscar_prefeitura(prefeitura_id):
    """Busca dados de uma prefeitura. Retorna dict ou None."""
    with gprb_cursor() as cur:
        tem_email = coluna_existe(cur, 'prefeitura', 'email')
        if tem_email:
            cur.execute('SELECT id, nome, sigla, regiao, prefeito, telefone, email FROM prefeitura WHERE id = %s', (prefeitura_id,))
        else:
            cur.execute('SELECT id, nome, sigla, regiao, prefeito, telefone FROM prefeitura WHERE id = %s', (prefeitura_id,))
        r = cur.fetchone()
        if r is None:
            return None
        return {
            'id': r[0], 'nome': r[1], 'sigla': r[2] or '', 'regiao': r[3],
            'prefeito': r[4] or '', 'telefone': r[5] or '',
            'email': r[6] or '' if tem_email else '',
            'tem_email': tem_email,
        }


def atualizar_prefeitura(prefeitura_id, dados):
    """Atualiza uma prefeitura."""
    with gprb_cursor() as cur:
        tem_email = coluna_existe(cur, 'prefeitura', 'email')
        if tem_email:
            cur.execute(
                'UPDATE prefeitura SET nome = %s, sigla = %s, prefeito = %s, telefone = %s, email = %s, "updatedAt" = NOW() WHERE id = %s',
                (dados['nome'], dados.get('sigla') or None, dados.get('prefeito') or None,
                 dados.get('telefone') or None, dados.get('email') or None, prefeitura_id),
            )
        else:
            cur.execute(
                'UPDATE prefeitura SET nome = %s, sigla = %s, prefeito = %s, telefone = %s, "updatedAt" = NOW() WHERE id = %s',
                (dados['nome'], dados.get('sigla') or None, dados.get('prefeito') or None,
                 dados.get('telefone') or None, prefeitura_id),
            )
        cur.connection.commit()


def contar_lojas_prefeitura(prefeitura_id):
    """Conta lojas vinculadas a uma prefeitura."""
    with gprb_cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM loja WHERE "prefeituraId" = %s', (prefeitura_id,))
        return cur.fetchone()[0]


def excluir_prefeitura(prefeitura_id):
    """Exclui uma prefeitura."""
    with gprb_cursor() as cur:
        cur.execute('DELETE FROM prefeitura WHERE id = %s', (prefeitura_id,))
        cur.connection.commit()


# ---------------------------------------------------------------------------
# Selects auxiliares (para formularios de membro)
# ---------------------------------------------------------------------------

def listar_classes():
    """Lista classes (MX, EN, CBCS) para select."""
    with gprb_cursor() as cur:
        cur.execute('SELECT id, name, abbreviation FROM class ORDER BY name')
        return [{'id': str(r[0]), 'name': r[1], 'abbr': r[2]} for r in cur.fetchall()]


def listar_lojas_select():
    """Lista lojas para select (form de membro)."""
    with gprb_cursor() as cur:
        cur.execute(
            'SELECT id, COALESCE("nomeFantasia", "lojaMX", \'Loja \' || numero::text) '
            'FROM loja ORDER BY 2'
        )
        return [{'id': str(r[0]), 'nome': r[1]} for r in cur.fetchall()]


def valores_distintos(coluna):
    """Retorna valores distintos de uma coluna do member (para autocomplete)."""
    if coluna not in _COLUNAS_MEMBER_PERMITIDAS:
        raise ValueError(f'Coluna nao permitida: {coluna}')
    with gprb_cursor() as cur:
        cur.execute(
            f'SELECT DISTINCT "{coluna}" FROM member '  # nosec B608
            f'WHERE "{coluna}" IS NOT NULL AND "{coluna}" <> \'\' ORDER BY 1'
        )
        return [r[0] for r in cur.fetchall()]


def sugestoes_membro():
    """Retorna dict com valores distintos para autocomplete do form de membro."""
    colunas = {
        'ritos': 'rito',
        'potencias': 'potencia_simbolismo',
        'cargos': 'cargo',
        'tipos_admissao': 'tipoAdmissao',
        'escolaridades': 'escolaridade',
        'estados_civis': 'estadoCivil',
    }
    return {chave: valores_distintos(coluna) for chave, coluna in colunas.items()}
