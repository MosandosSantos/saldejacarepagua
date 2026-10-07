"""Autenticação e gestão de usuários do sistema GPRB."""

import bcrypt

from core.gprb.connection import _DummyConnection, connect


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


def label_role_gprb(role):
    """Rótulo legível de um perfil GPRB."""
    if not role:
        return '—'
    return ROLE_LABELS_GPRB.get(role, role.replace('_', ' ').title())


def autenticar_usuario(identifier, senha, tenant_code='GPRB'):
    """Autentica um usuario pelo loginIdentifier (telefone/email) contra o banco GPRB.

    Retorna dict com dados do usuario ou None se falhar:
        {'id': ..., 'name': ..., 'email': ..., 'role': ..., 'tenant_id': ...}
    """
    conn = connect()
    if isinstance(conn, _DummyConnection):
        # Modo degradado (specs/legacy/database.md): sem banco GPRB a
        # autenticação cai no espelho local — sem erro/log de exceção.
        return None
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
        if not bcrypt.checkpw(senha.encode('utf-8'), password_hash.encode('utf-8')):
            return None
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
    if isinstance(conn, _DummyConnection):
        # Modo degradado: nenhum usuário GPRB consultável — o login usa o
        # espelho local (True aqui bloquearia todo login local).
        return False
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


def listar_usuarios_sistema(tenant_code='GPRB', *, q='', loja_id='', perfil='', status=''):
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
