"""Repository para o banco de dados GPRB (PostgreSQL externo).

Centraliza todas as queries SQL que antes estavam espalhadas em views.
Cada metodo encapsula uma operacao: abre conexao, executa, fecha.
"""
import uuid
from contextlib import contextmanager

from core.gprb import coluna_existe, connect
from core.gprb.connection import gprb_transaction


@contextmanager
def gprb_cursor():
    """Context manager que abre e fecha conexao GPRB automaticamente."""
    from core.gprb.connection import _DummyConnection
    conn = connect()
    try:
        yield conn.cursor()
    finally:
        conn.close()


class _DummyCursor:
    """Cursor fictício — retorna vazio quando o banco GPRB indisponível."""
    description = None  # DB-API: sem conjunto de resultados (modo degradado)
    def execute(self, *a, **kw): pass
    def fetchone(self): return (0,)
    def fetchall(self): return []
    def __enter__(self): return self
    def __exit__(self, *a): pass


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
    """Retorna o id do tenant GPRB (None se indisponível)."""
    with gprb_cursor() as cur:
        cur.execute("SELECT id FROM tenant WHERE code = 'GPRB'")
        row = cur.fetchone()
        tid = row[0] if row else None
        if tid == 0:
            tid = None
        return tid


# ---------------------------------------------------------------------------
# Membros
# ---------------------------------------------------------------------------

def buscar_membro(member_id):
    """Busca um membro pelo ID — todos os campos da ficha + lojas (N:N)."""
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
           m."condicao_mensalidade", m."lojaId",
           m."createdAt", m."updatedAt",
           l."nomeFantasia", l.numero as loja_numero,
           p.nome as prefeitura_nome, p.sigla as prefeitura_sigla
        FROM member m
        LEFT JOIN loja l ON m."lojaId" = l.id
        LEFT JOIN prefeitura p ON l."prefeituraId" = p.id
        WHERE m.id = %s
        ''', (member_id,))
        row = cur.fetchone()
        if row is None:
            return None
        membro = {
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
            'loja_id': row[38] or '',
            'criado_em': row[39], 'atualizado_em': row[40],
            'loja': row[41] or (f'Loja {row[42]}' if row[42] else '—'),
            'prefeitura': row[43] or row[44] or '—',
        }
        membro['lojas'] = lojas_do_membro(member_id)
        membro['lojas_ids'] = [l['id'] for l in membro['lojas']]
        return membro


def atualizar_membro(member_id, dados):
    """Atualiza um membro no banco GPRB. `dados` e um dict com as colunas.

    Aceita chaves com ou sem aspas (ex.: '"nomeCompleto"' ou 'email').
    """
    with gprb_transaction(), gprb_cursor() as cur:
        colunas = ', '.join(f'"{k.strip(chr(34))}" = %s' for k in dados)
        valores = list(dados.values()) + [member_id]
        cur.execute(f'UPDATE member SET {colunas}, "updatedAt" = NOW() WHERE id = %s', valores)  # nosec B608


def inativar_membro(member_id):
    """Marca membro como INATIVO."""
    with gprb_transaction(), gprb_cursor() as cur:
        cur.execute(
            'UPDATE member SET situacao = %s, "updatedAt" = NOW() WHERE id = %s',
            ('INATIVO', member_id),
        )


def excluir_membro(member_id):
    """Exclui um membro do banco GPRB."""
    with gprb_transaction(), gprb_cursor() as cur:
        cur.execute('DELETE FROM member WHERE id = %s', (member_id,))


def lojas_do_membro(member_id):
    """Lojas de um membro (relacao N:N via member_loja, PK composta).

    Retorna lista de dicts: {'id', 'nome', 'numero', 'prefeitura',
    'prefeitura_sigla', 'data_inclusao'}.
    """
    with gprb_cursor() as cur:
        cur.execute('''
        SELECT l.id,
               COALESCE(l."nomeFantasia", l."lojaMX", 'Loja ' || COALESCE(l.numero::text, '')) as nome,
               l.numero, p.nome as prefeitura, p.sigla as prefeitura_sigla,
               ml."dataInclusao"
        FROM member_loja ml
        JOIN loja l ON ml."lojaId" = l.id
        LEFT JOIN prefeitura p ON l."prefeituraId" = p.id
        WHERE ml."memberId" = %s
        ORDER BY ml."dataInclusao", 2
        ''', (member_id,))
        return [
            {
                'id': r[0], 'nome': r[1] or '—', 'numero': r[2],
                'prefeitura': r[3] or '—', 'prefeitura_sigla': r[4] or '',
                'data_inclusao': r[5],
            }
            for r in cur.fetchall()
        ]


def definir_lojas_membro(member_id, loja_ids, datas_inclusao=None):
    """Define as lojas de um membro (substitui a relacao N:N).

    `datas_inclusao` (opcional) mapeia loja_id -> date de inclusao; lojas
    ja presentes mantem a data original quando nao informado. A primeira
    loja da lista vira a loja principal (coluna member."lojaId"), mantendo
    as consultas legadas do sistema GPRB funcionando.
    """
    loja_ids = [str(x) for x in (loja_ids or []) if x]
    datas_inclusao = datas_inclusao or {}
    with gprb_transaction(), gprb_cursor() as cur:
        cur.execute('SELECT "lojaId", "dataInclusao" FROM member_loja WHERE "memberId" = %s', (member_id,))
        atuais = {r[0]: r[1] for r in cur.fetchall()}
        cur.execute('DELETE FROM member_loja WHERE "memberId" = %s', (member_id,))
        for loja_id in dict.fromkeys(loja_ids):  # dedup preservando ordem
            data = datas_inclusao.get(loja_id) or atuais.get(loja_id)
            if data:
                cur.execute(
                    'INSERT INTO member_loja ("memberId", "lojaId", "dataInclusao") VALUES (%s, %s, %s) '
                    'ON CONFLICT ("memberId", "lojaId") DO NOTHING',
                    (member_id, loja_id, data),
                )
            else:
                cur.execute(
                    'INSERT INTO member_loja ("memberId", "lojaId") VALUES (%s, %s) '
                    'ON CONFLICT ("memberId", "lojaId") DO NOTHING',
                    (member_id, loja_id),
                )
        principal = loja_ids[0] if loja_ids else None
        cur.execute(
            'UPDATE member SET "lojaId" = %s, "updatedAt" = NOW() WHERE id = %s',
            (principal, member_id),
        )


def listar_membros_filtros():
    """Retorna opcoes para os filtros da listagem de membros."""
    tid = _obter_tenant_gprb()
    if tid is None:
        return {'prefeituras': [], 'lojas': [], 'ufs': [], 'cidades': []}
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

        return {
            'prefeituras': prefeituras,
            'lojas': lojas,
            'ufs': ufs,
            'cidades': cidades,
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
        where += (' AND (p.id = %s OR EXISTS (SELECT 1 FROM member_loja mlx '
                  'JOIN loja lx ON mlx."lojaId" = lx.id '
                  'WHERE mlx."memberId" = m.id AND lx."prefeituraId" = %s))')
        params.append(filtros['prefeitura_id'])
        params.append(filtros['prefeitura_id'])
    if filtros.get('loja_id'):
        where += (' AND (m."lojaId" = %s OR m.id IN '
                  '(SELECT "memberId" FROM member_loja WHERE "lojaId" = %s))')
        params.append(filtros['loja_id'])
        params.append(filtros['loja_id'])
    if filtros.get('uf'):
        where += ' AND m."enderecoUf" = %s'
        params.append(filtros['uf'])
    if filtros.get('cidade'):
        where += " AND REPLACE(COALESCE(m.\"enderecoCidade\", ''), chr(65533), '') = %s"
        params.append(filtros['cidade'])
    if filtros.get('grau'):
        pass  # filtro de grau/classe removido (classes nao se aplicam ao projeto)

    with gprb_cursor() as cur:
        sql = '''
        SELECT m.id, m."nomeCompleto", m.email, m.celular, m.cpf,
           m."enderecoCidade", m."enderecoUf", m.situacao,
           l."nomeFantasia", l.numero as loja_numero,
           p.nome as prefeitura_nome, p.sigla as prefeitura_sigla,
           m."createdAt",
           (SELECT MAX(pp.year) FROM payment_status ps2
            JOIN payment_period pp ON ps2."periodId" = pp.id
            WHERE ps2."memberId" = m.id AND pp.type = 'ANNUAL'
              AND ps2.status = 'PAID') as ultima_anuidade,
           (SELECT COALESCE(json_agg(json_build_object(
                        'loja', COALESCE(l2."nomeFantasia", l2."lojaMX",
                                 'Loja ' || COALESCE(l2.numero::text, '')),
                        'potencia', p2.nome, 'sigla', p2.sigla)
                    ORDER BY l2."nomeFantasia"), '[]'::json)
              FROM member_loja ml2
              JOIN loja l2 ON ml2."lojaId" = l2.id
              LEFT JOIN prefeitura p2 ON l2."prefeituraId" = p2.id
             WHERE ml2."memberId" = m.id) as lojas_drill,
           m."dataNascimento"
        FROM member m
        JOIN tenant t ON m."tenantId" = t.id
        LEFT JOIN loja l ON m."lojaId" = l.id
        LEFT JOIN prefeitura p ON l."prefeituraId" = p.id
        {where}
        ORDER BY m."createdAt" DESC
        '''
        # nosec abaixo: {where} e estrutura interna montada neste modulo; valores sempre em params
        cur.execute(sql.replace('{where}', where), params)  # nosec B608
        return cur.fetchall()


# ---------------------------------------------------------------------------
# Lojas
# ---------------------------------------------------------------------------

def membros_por_situacao(tenant_code='GPRB', apenas_ativos=True, ano=None):
    """Contagem de membros por situacao (ATIVO/INATIVO), N:N-aware.

    Substitui membros_por_classe (classes nao se aplicam ao projeto).
    Retorna [{'name': 'ATIVO', 'total': n}, ...].
    """
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
    with gprb_cursor() as cur:
        cur.execute(
            f'SELECT m.situacao, COUNT(m.id) as total FROM member m '
            f'JOIN tenant t ON m."tenantId" = t.id WHERE {where} '
            f'GROUP BY m.situacao ORDER BY 2 DESC',  # nosec B608
            params,
        )
        return [{'name': r[0] or 'INATIVO', 'total': r[1]} for r in cur.fetchall()]


def _formatar_moeda(v):
    """Formata Decimal/numeric como texto BR ('1.500,00'); '' quando vazio."""
    if v is None:
        return ''
    try:
        return f'{float(v):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    except (TypeError, ValueError):
        return ''


def listar_lojas(termo=''):
    """Lista lojas com contagem de membros. Retorna (lojas_list, total)."""
    tid = _obter_tenant_gprb()
    if tid is None:
        return [], 0
    where = 'WHERE l."tenantId" = %s'
    params = [tid]
    if termo:
        where += ' AND (l."nomeFantasia" ILIKE %s OR l.numero::text ILIKE %s)'
        params.extend([f'%{termo}%', f'%{termo}%'])

    with gprb_cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM loja l {where}', params)  # nosec B608
        total = cur.fetchone()[0]

        sql = '''
        SELECT l.id, l."nomeFantasia", l.numero, l.telefone, l.email,
               l."enderecoCidade", l."enderecoUf", l.situacao,
               p.nome as prefeitura_nome,
               COUNT(DISTINCT m.id) as total_membros,
               l."mensalidade_regular"
        FROM loja l
        LEFT JOIN prefeitura p ON l."prefeituraId" = p.id
        LEFT JOIN member m ON (m."lojaId" = l.id OR m.id IN (SELECT "memberId" FROM member_loja WHERE "lojaId" = l.id))
        {where}
        GROUP BY l.id, l."nomeFantasia", l.numero, l.telefone, l.email,
                 l."enderecoCidade", l."enderecoUf", l.situacao,
                 p.nome
        ORDER BY l."nomeFantasia"
        '''
        # nosec abaixo: {where} e estrutura interna montada neste modulo; valores sempre em params
        cur.execute(sql.replace('{where}', where), params)  # nosec B608
        lojas_list = [
            {
                'id': r[0], 'nome': r[1] or f'Loja {r[2]}', 'numero': r[2],
                'telefone': r[3] or '—', 'email': r[4] or '—',
                'cidade': r[5] or '', 'uf': r[6] or '',
                'situacao': r[7] or '',
                'prefeitura': r[8] or '—',
                'total_membros': r[9],
                'mensalidade': _formatar_moeda(r[10]),
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
        secretarias = {}
        if coluna_existe(cur, 'loja', 'secretarioNome'):
            cur.execute(
                'SELECT l.id, l."secretarioNome", l."tesoureiroNome" '
                'FROM loja l ' + where,
                params,
            )
            secretarias = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
        for loja in lojas_list:
            loja['deputado_mestre'] = deputados.get(loja['id']) or '—'
            sec, tes = secretarias.get(loja['id']) or ('', '')
            loja['secretario'] = sec or '—'
            loja['tesoureiro'] = tes or '—'

        return lojas_list, total


def buscar_loja(loja_id):
    """Busca detalhe de uma loja. Retorna dict ou None."""
    with gprb_cursor() as cur:
        cur.execute('''
        SELECT l.id, l."nomeFantasia", l.numero, l.telefone, l.email,
           l."enderecoLogradouro", l."enderecoNumero", l."enderecoBairro",
           l."enderecoCidade", l."enderecoUf", l."enderecoCep",
           l.situacao, l."dataFundacao",
           p.nome as prefeitura,
           l."mensalidade_regular"
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
            'prefeitura': r[13] or '—',
            'mensalidade': _formatar_moeda(r[14]),
        }
        cur.execute(
            'SELECT COUNT(DISTINCT m.id) FROM member m '
            'WHERE m."lojaId" = %s OR m.id IN (SELECT "memberId" FROM member_loja WHERE "lojaId" = %s)',
            (loja_id, loja_id),
        )
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

        loja['secretario'] = '—'
        loja['tesoureiro'] = '—'
        loja['secretario_telefone'] = ''
        loja['tesoureiro_telefone'] = ''
        if coluna_existe(cur, 'loja', 'secretarioNome'):
            cur.execute(
                'SELECT "secretarioNome", "secretarioTelefone", '
                '"tesoureiroNome", "tesoureiroTelefone" FROM loja WHERE id = %s',
                (loja_id,),
            )
            s_row = cur.fetchone()
            if s_row:
                loja['secretario'] = s_row[0] or '—'
                loja['tesoureiro'] = s_row[2] or '—'
                loja['secretario_telefone'] = s_row[1] or ''
                loja['tesoureiro_telefone'] = s_row[3] or ''
        return loja


def criar_loja(dados):
    """Insere uma nova loja. `dados` e um dict com os campos.

    Colunas NOT NULL obrigatorias do schema:
    - "lojaMX": codigo alternativo — usa o nome informado quando vazio;
    - "prefeituraId": FK obrigatoria — o form ja envia a potencia selecionada.

    Campos de diretoria (secretario/tesoureiro) e mensalidade sao gravados
    apenas se as colunas existirem no banco (guard coluna_existe, mesmo
    padrao de atualizar_loja).
    """
    tid = _obter_tenant_gprb()
    if tid is None:
        return None
    prefeitura_id = (dados.get('prefeitura_id') or '').strip() or None
    if not prefeitura_id:
        raise ValueError('A Potência (prefeitura) e obrigatoria para a loja.')
    loja_id = str(uuid.uuid4())
    with gprb_transaction(), gprb_cursor() as cur:
        cur.execute('''
        INSERT INTO loja (id, "tenantId", "lojaMX", "nomeFantasia", numero, telefone, email,
        "prefeituraId", "enderecoLogradouro", "enderecoCidade", "enderecoUf", "mensalidade_regular", situacao,
        "createdAt", "updatedAt")
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ATIVA', NOW(), NOW())
        ''', (
            loja_id, tid,
            dados['nome'],
            dados['nome'],
            int(dados['numero']) if dados.get('numero', '').isdigit() else None,
            dados.get('telefone') or None,
            dados.get('email') or None,
            prefeitura_id,
            dados.get('endereco') or None,
            dados.get('cidade') or None,
            dados.get('uf') or None,
            dados.get('mensalidade') or None,
        ))
        # Diretoria — so grava quando o schema tiver as colunas (schema compartilhado varia).
        if (dados.get('secretario_nome') or dados.get('secretario_telefone')
                or dados.get('tesoureiro_nome') or dados.get('tesoureiro_telefone')):
            if coluna_existe(cur, 'loja', 'secretarioNome'):
                cur.execute('''
                UPDATE loja SET
                    "secretarioNome" = %s, "secretarioTelefone" = %s,
                    "tesoureiroNome" = %s, "tesoureiroTelefone" = %s,
                    "updatedAt" = NOW()
                WHERE id = %s
                ''', (
                    dados.get('secretario_nome') or None,
                    dados.get('secretario_telefone') or None,
                    dados.get('tesoureiro_nome') or None,
                    dados.get('tesoureiro_telefone') or None,
                    loja_id,
                ))


def atualizar_loja(loja_id, dados):
    """Atualiza uma loja. `dados` e um dict com os campos."""
    with gprb_transaction(), gprb_cursor() as cur:
        if coluna_existe(cur, 'loja', 'deputadoMestreId'):
            cur.execute('''
            UPDATE loja SET "nomeFantasia" = %s, telefone = %s, email = %s,
                "prefeituraId" = %s, "enderecoLogradouro" = %s,
                "enderecoCidade" = %s, "enderecoUf" = %s,
                "mensalidade_regular" = %s,
                "deputadoMestreId" = %s, "updatedAt" = NOW()
            WHERE id = %s
            ''', (
                dados['nome'],
                dados.get('telefone') or None,
                dados.get('email') or None,
                dados.get('prefeitura_id') or None,
                dados.get('endereco') or None,
                dados.get('cidade') or None,
                dados.get('uf') or None,
                dados.get('mensalidade') or None,
                dados.get('deputado_mestre') or None,
                loja_id,
            ))
        else:
            cur.execute('''
            UPDATE loja SET "nomeFantasia" = %s, telefone = %s, email = %s,
                "prefeituraId" = %s, "enderecoLogradouro" = %s,
                "enderecoCidade" = %s, "enderecoUf" = %s,
                "mensalidade_regular" = %s,
                "updatedAt" = NOW()
            WHERE id = %s
            ''', (
                dados['nome'],
                dados.get('telefone') or None,
                dados.get('email') or None,
                dados.get('prefeitura_id') or None,
                dados.get('endereco') or None,
                dados.get('cidade') or None,
                dados.get('uf') or None,
                dados.get('mensalidade') or None,
                loja_id,
            ))

        # Diretoria — so grava quando o schema tiver as colunas.
        if coluna_existe(cur, 'loja', 'secretarioNome'):
            cur.execute('''
            UPDATE loja SET "secretarioNome" = %s, "secretarioTelefone" = %s,
                "tesoureiroNome" = %s, "tesoureiroTelefone" = %s,
                "updatedAt" = NOW()
            WHERE id = %s
            ''', (
                dados.get('secretario_nome') or None,
                dados.get('secretario_telefone') or None,
                dados.get('tesoureiro_nome') or None,
                dados.get('tesoureiro_telefone') or None,
                loja_id,
            ))


def contar_membros_loja(loja_id):
    """Conta quantos membros pertencem a uma loja (relacao N:N)."""
    with gprb_cursor() as cur:
        cur.execute(
            'SELECT COUNT(*) FROM member WHERE "lojaId" = %s '
            'OR id IN (SELECT "memberId" FROM member_loja WHERE "lojaId" = %s)',
            (loja_id, loja_id),
        )
        return cur.fetchone()[0]


def excluir_loja(loja_id):
    """Exclui uma loja."""
    with gprb_transaction(), gprb_cursor() as cur:
        cur.execute('DELETE FROM loja WHERE id = %s', (loja_id,))


def buscar_loja_para_edicao(loja_id):
    """Busca dados de loja para o formulario de edicao."""
    with gprb_cursor() as cur:
        cur.execute('''
        SELECT l.id, l."nomeFantasia", l.numero, l.telefone, l.email,
           l."prefeituraId", l."enderecoCidade", l."enderecoUf", l.situacao,
           l."enderecoLogradouro", l."mensalidade_regular"
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
            'endereco': r[9] or '', 'mensalidade': _formatar_moeda(r[10]),
        }
        tid = _obter_tenant_gprb()
        cur.execute('SELECT id, nome FROM prefeitura WHERE "tenantId" = %s ORDER BY nome', (tid,))
        prefeituras = [{'id': pr[0], 'nome': pr[1]} for pr in cur.fetchall()]
        cur.execute(
            'SELECT id, "nomeCompleto" FROM member '
            'WHERE ("lojaId" = %s OR id IN (SELECT "memberId" FROM member_loja WHERE "lojaId" = %s)) '
            'AND situacao = %s ORDER BY "nomeCompleto"',
            (loja_id, loja_id, 'ATIVO'),
        )
        membros = [{'id': mr[0], 'nome': mr[1]} for mr in cur.fetchall()]

        loja['deputado_mestre_id'] = ''
        if coluna_existe(cur, 'loja', 'deputadoMestreId'):
            cur.execute('SELECT "deputadoMestreId" FROM loja WHERE id = %s', (loja_id,))
            dm_row = cur.fetchone()
            loja['deputado_mestre_id'] = (dm_row[0] or '') if dm_row else ''

        loja['secretario_nome'] = ''
        loja['secretario_telefone'] = ''
        loja['tesoureiro_nome'] = ''
        loja['tesoureiro_telefone'] = ''
        if coluna_existe(cur, 'loja', 'secretarioNome'):
            cur.execute(
                'SELECT "secretarioNome", "secretarioTelefone", '
                '"tesoureiroNome", "tesoureiroTelefone" FROM loja WHERE id = %s',
                (loja_id,),
            )
            s_row = cur.fetchone()
            if s_row:
                loja['secretario_nome'] = s_row[0] or ''
                loja['secretario_telefone'] = s_row[1] or ''
                loja['tesoureiro_nome'] = s_row[2] or ''
                loja['tesoureiro_telefone'] = s_row[3] or ''

        return loja, prefeituras, membros


def listar_lojas_para_select():
    """Lista lojas para selects (usado em formularios de loja nova)."""
    tid = _obter_tenant_gprb()
    if tid is None:
        return []
    with gprb_cursor() as cur:
        cur.execute('SELECT id, nome FROM prefeitura WHERE "tenantId" = %s ORDER BY nome', (tid,))
        return [{'id': r[0], 'nome': r[1]} for r in cur.fetchall()]


def listar_membros_loja(loja_id):
    """Lista membros de uma loja (relacao N:N, para drill-down JSON)."""
    with gprb_cursor() as cur:
        cur.execute('''
        SELECT m.id, m."nomeCompleto", m.situacao, m."dataIniciacao"
        FROM member m
        WHERE m."lojaId" = %s OR m.id IN (SELECT "memberId" FROM member_loja WHERE "lojaId" = %s)
        ORDER BY m.situacao, m."nomeCompleto"
        ''', (loja_id, loja_id))
        return [
            {
                'id': r[0], 'nome': r[1] or '',
                'situacao': r[2] or '',
            }
            for r in cur.fetchall()
        ]


def listar_lojas_por_prefeitura(prefeitura_id):
    """Lista lojas de uma prefeitura (para drill-down JSON)."""
    with gprb_cursor() as cur:
        cur.execute('''
        SELECT l.id, l."nomeFantasia", l."lojaMX", l.numero, l.situacao,
           COUNT(m.id) as membros
        FROM loja l
        LEFT JOIN member m ON (m."lojaId" = l.id OR m.id IN (SELECT "memberId" FROM member_loja WHERE "lojaId" = l.id)) AND m.situacao = 'ATIVO'
        WHERE l."prefeituraId" = %s
        GROUP BY l.id, l."nomeFantasia", l."lojaMX", l.numero, l.situacao
        ORDER BY l."nomeFantasia"
        ''', (prefeitura_id,))
        return [
            {
                'id': r[0], 'nome': r[1] or r[2] or f'Loja #{r[3]}',
                'loja_mx': r[2] or '', 'numero': r[3],
                'situacao': r[4], 'total_membros': r[5],
            }
            for r in cur.fetchall()
        ]


# ---------------------------------------------------------------------------
# Prefeituras
# ---------------------------------------------------------------------------

def _fmt_moeda(valor):
    """Decimal → 'R$ 1.234,56' (vazio se None)."""
    if valor is None:
        return ''
    try:
        texto = f'{float(valor):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        return f'R$ {texto}'
    except (TypeError, ValueError):
        return ''


def _fmt_data_br(d):
    """date → 'dd/mm/aaaa' (vazio se None)."""
    return d.strftime('%d/%m/%Y') if d else ''


def listar_prefeituras():
    """Lista prefeituras com KPIs. Retorna (prefeituras, total_pf, total_lojas, total_membros)."""
    tid = _obter_tenant_gprb()
    if tid is None:
        return [], 0, 0, 0
    with gprb_cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM prefeitura WHERE "tenantId" = %s', (tid,))
        total_pf = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM loja WHERE "tenantId" = %s', (tid,))
        total_lojas = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM member WHERE "tenantId" = %s', (tid,))
        total_membros = cur.fetchone()[0]

        cur.execute('''
        SELECT p.id, p.nome, p.sigla, p.prefeito, p.telefone, p.email,
               p."secretarioEmail", p."secretarioTelefone",
               p."tesoureiroEmail", p."tesoureiroTelefone",
               p.pix, p."valorAnuidade", p."dataVencimentoAnuidade",
               COUNT(DISTINCT l.id) as total_lojas,
               COUNT(DISTINCT m.id) as total_membros
        FROM prefeitura p
        LEFT JOIN loja l ON l."prefeituraId" = p.id
        LEFT JOIN member m ON (m."lojaId" = l.id OR m.id IN (SELECT "memberId" FROM member_loja WHERE "lojaId" = l.id)) AND m.situacao = 'ATIVO'
        WHERE p."tenantId" = %s
        GROUP BY p.id, p.nome, p.sigla, p.prefeito, p.telefone, p.email,
                 p."secretarioEmail", p."secretarioTelefone",
                 p."tesoureiroEmail", p."tesoureiroTelefone",
                 p.pix, p."valorAnuidade", p."dataVencimentoAnuidade"
        ORDER BY p.nome
        ''', (tid,))
        prefeituras_list = [
            {
                'id': r[0], 'nome': r[1], 'sigla': r[2] or '',
                'prefeito': r[3] or '—', 'telefone': r[4] or '—',
                'email': r[5] or '',
                'secretario_email': r[6] or '', 'secretario_telefone': r[7] or '',
                'tesoureiro_email': r[8] or '', 'tesoureiro_telefone': r[9] or '',
                'pix': r[10] or '',
                'valor_anuidade': r[11], 'valor_anuidade_fmt': _fmt_moeda(r[11]),
                'vencimento_anuidade': r[12], 'vencimento_fmt': _fmt_data_br(r[12]),
                'total_lojas': r[13], 'total_membros': r[14],
            }
            for r in cur.fetchall()
        ]

        return prefeituras_list, total_pf, total_lojas, total_membros


def criar_prefeitura(dados):
    """Insere uma nova prefeitura com contatos de cargo e dados financeiros."""
    tid = _obter_tenant_gprb()
    if tid is None:
        return None
    with gprb_transaction(), gprb_cursor() as cur:
        cur.execute('''
        INSERT INTO prefeitura (id, "tenantId", nome, sigla, prefeito, telefone, email,
            "secretarioEmail", "secretarioTelefone", "tesoureiroEmail", "tesoureiroTelefone",
            pix, "valorAnuidade", "dataVencimentoAnuidade", status, "createdAt", "updatedAt")
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ATIVA', NOW(), NOW())
        ''', (
            str(uuid.uuid4()), tid,
            dados['nome'], dados.get('sigla') or None,
            dados.get('prefeito') or None, dados.get('telefone') or None,
            dados.get('email') or None,
            dados.get('secretario_email') or None,
            dados.get('secretario_telefone') or None,
            dados.get('tesoureiro_email') or None,
            dados.get('tesoureiro_telefone') or None,
            dados.get('pix') or None,
            dados.get('valor_anuidade') or None,
            dados.get('vencimento_anuidade') or None,
        ))


def buscar_prefeitura(prefeitura_id):
    """Busca dados de uma prefeitura. Retorna dict ou None."""
    with gprb_cursor() as cur:
        cur.execute('''
        SELECT id, nome, sigla, prefeito, telefone, email,
               "secretarioEmail", "secretarioTelefone", "tesoureiroEmail", "tesoureiroTelefone",
               pix, "valorAnuidade", "dataVencimentoAnuidade"
        FROM prefeitura WHERE id = %s''', (prefeitura_id,))
        r = cur.fetchone()
        if r is None:
            return None
        return {
            'id': r[0], 'nome': r[1], 'sigla': r[2] or '',
            'prefeito': r[3] or '', 'telefone': r[4] or '',
            'email': r[5] or '',
            'secretario_email': r[6] or '', 'secretario_telefone': r[7] or '',
            'tesoureiro_email': r[8] or '', 'tesoureiro_telefone': r[9] or '',
            'pix': r[10] or '',
            'valor_anuidade': r[11], 'valor_fmt': _fmt_moeda(r[11]),
            'vencimento_anuidade': r[12],
            'vencimento_iso': r[12].isoformat() if r[12] else '',
        }


def atualizar_prefeitura(prefeitura_id, dados):
    """Atualiza uma prefeitura (exibida como Potencia)."""
    with gprb_transaction(), gprb_cursor() as cur:
        cur.execute('''
        UPDATE prefeitura SET nome = %s, sigla = %s, prefeito = %s, telefone = %s, email = %s,
               "secretarioEmail" = %s, "secretarioTelefone" = %s,
               "tesoureiroEmail" = %s, "tesoureiroTelefone" = %s,
               pix = %s, "valorAnuidade" = %s, "dataVencimentoAnuidade" = %s,
               "updatedAt" = NOW()
        WHERE id = %s''', (
            dados['nome'], dados.get('sigla') or None, dados.get('prefeito') or None,
            dados.get('telefone') or None, dados.get('email') or None,
            dados.get('secretario_email') or None,
            dados.get('secretario_telefone') or None,
            dados.get('tesoureiro_email') or None,
            dados.get('tesoureiro_telefone') or None,
            dados.get('pix') or None,
            dados.get('valor_anuidade') or None,
            dados.get('vencimento_anuidade') or None,
            prefeitura_id,
        ))


def contar_lojas_prefeitura(prefeitura_id):
    """Conta lojas vinculadas a uma prefeitura."""
    with gprb_cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM loja WHERE "prefeituraId" = %s', (prefeitura_id,))
        return cur.fetchone()[0]


def excluir_prefeitura(prefeitura_id):
    """Exclui uma prefeitura."""
    with gprb_transaction(), gprb_cursor() as cur:
        cur.execute('DELETE FROM prefeitura WHERE id = %s', (prefeitura_id,))


# ---------------------------------------------------------------------------
# Selects auxiliares (para formularios de membro)
# ---------------------------------------------------------------------------


def listar_lojas_select():
    """Lista lojas (com sua potencia) para select (form de membro)."""
    with gprb_cursor() as cur:
        cur.execute(
            'SELECT l.id, COALESCE(l."nomeFantasia", l."lojaMX", \'Loja \' || l.numero::text), '
            'p.nome, p.sigla '
            'FROM loja l LEFT JOIN prefeitura p ON l."prefeituraId" = p.id ORDER BY 2'
        )
        return [
            {'id': str(r[0]), 'nome': r[1], 'prefeitura': r[2] or r[3] or ''}
            for r in cur.fetchall()
        ]


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
