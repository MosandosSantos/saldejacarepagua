"""Sonda temporária 12: espelho local de usuários (identificador de login)."""
import django, os
import psycopg

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from acesso.models import Usuario

print('Espelho local (Usuario):')
for u in Usuario.objects.order_by('pk'):
    print(f'  pk={u.pk} nome={u.nome!r} email={u.email!r} '
          f'celular={u.celular!r} role={u.role} tenant={u.tenant_id} '
          f'status={u.status}')

# Tenta listar o banco GPRB (pode cair no modo degradado)
try:
    from core.gprb.connection import _DummyConnection, connect
    conn = connect()
    if isinstance(conn, _DummyConnection):
        print('\nGPRB: modo degradado (dummy) — login local apenas.')
    else:
        cur = conn.cursor()
        cur.execute(
            'SELECT u.id, u."name", u.email, u."loginIdentifier", u.role, t.code '
            'FROM "user" u JOIN tenant t ON u."tenantId" = t.id '
            'WHERE u."deletedAt" IS NULL ORDER BY u."createdAt" LIMIT 30',
        )
        print('\nGPRB user:')
        for row in cur.fetchall():
            print(' ', row)
        conn.close()
except (psycopg.Error, OSError) as e:
    print('\nGPRB erro:', e)
