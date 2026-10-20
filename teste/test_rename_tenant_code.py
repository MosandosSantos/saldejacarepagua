import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from core.gprb import connection as gprb_connection

PROJECT_ROOT = Path(__file__).resolve().parents[1]

try:
    from scripts.renomear_codigo_tenant import renomear_codigo_tenant
except ImportError:
    renomear_codigo_tenant = None


@pytest.fixture
def tenant_codes(banco_gprb_teste):
    suffix = uuid4().hex
    dados = {
        'old_id': f'old-{suffix}',
        'old_code': f'GPRB_TEST_OLD_{suffix}',
        'new_code': f'SCG_TEST_NEW_{suffix}',
        'other_id': f'other-{suffix}',
        'other_code': f'KEEP_TEST_{suffix}',
    }
    conn = gprb_connection.connect()
    cur = conn.cursor()
    for key_id, key_code in (
        ('old_id', 'old_code'), ('other_id', 'other_code'),
    ):
        cur.execute(
            'INSERT INTO tenant (id, code, name, "createdAt", "updatedAt") '
            'VALUES (%s, %s, %s, NOW(), NOW())',
            (dados[key_id], dados[key_code], 'Tenant teste de rename'),
        )
    try:
        yield dados
    finally:
        cur.execute('DELETE FROM tenant WHERE id = %s', (dados['old_id'],))
        cur.execute('DELETE FROM tenant WHERE id = %s', (dados['other_id'],))
        conn.close()


def _rename(conn, old_code, new_code, *, apply=False):
    if renomear_codigo_tenant is None:
        pytest.fail('scripts.renomear_codigo_tenant is not implemented yet')
    return renomear_codigo_tenant(conn, old_code, new_code, apply=apply)


def test_rename_script_cli_loads_from_scripts_directory():
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / 'scripts' / 'renomear_codigo_tenant.py'), '--help'],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert '--apply' in result.stdout


@pytest.mark.django_db(transaction=True)
def test_rename_tenant_code_dry_run_does_not_write(tenant_codes):
    conn = gprb_connection.connect()
    cur = conn.cursor()

    returned_id = _rename(conn, tenant_codes['old_code'], tenant_codes['new_code'])

    assert returned_id == tenant_codes['old_id']
    cur.execute('SELECT code FROM tenant WHERE id = %s', (tenant_codes['old_id'],))
    assert cur.fetchone()[0] == tenant_codes['old_code']


@pytest.mark.django_db(transaction=True)
def test_rename_tenant_code_preserves_id_and_other_tenants(tenant_codes):
    conn = gprb_connection.connect()
    cur = conn.cursor()

    returned_id = _rename(
        conn, tenant_codes['old_code'], tenant_codes['new_code'], apply=True,
    )

    assert returned_id == tenant_codes['old_id']
    cur.execute('SELECT id FROM tenant WHERE code = %s', (tenant_codes['new_code'],))
    assert cur.fetchone()[0] == tenant_codes['old_id']
    cur.execute('SELECT code FROM tenant WHERE id = %s', (tenant_codes['other_id'],))
    assert cur.fetchone()[0] == tenant_codes['other_code']


@pytest.mark.django_db(transaction=True)
def test_rename_tenant_code_rejects_missing_old_code(tenant_codes):
    conn = gprb_connection.connect()

    with pytest.raises(ValueError):
        _rename(conn, 'MISSING_CODE', tenant_codes['new_code'], apply=True)


@pytest.mark.django_db(transaction=True)
def test_rename_tenant_code_rejects_duplicate_old_code(tenant_codes):
    conn = gprb_connection.connect()
    cur = conn.cursor()
    duplicate_id = f'duplicate-{uuid4().hex}'
    cur.execute(
        'INSERT INTO tenant (id, code, name, "createdAt", "updatedAt") '
        'VALUES (%s, %s, %s, NOW(), NOW())',
        (duplicate_id, tenant_codes['old_code'], 'Duplicate tenant test'),
    )
    try:
        with pytest.raises(ValueError):
            _rename(conn, tenant_codes['old_code'], tenant_codes['new_code'], apply=True)
    finally:
        cur.execute('DELETE FROM tenant WHERE id = %s', (duplicate_id,))


@pytest.mark.django_db(transaction=True)
def test_rename_tenant_code_rejects_existing_new_code(tenant_codes):
    conn = gprb_connection.connect()
    cur = conn.cursor()
    target_id = f'target-{uuid4().hex}'
    cur.execute(
        'INSERT INTO tenant (id, code, name, "createdAt", "updatedAt") '
        'VALUES (%s, %s, %s, NOW(), NOW())',
        (target_id, tenant_codes['new_code'], 'Target tenant test'),
    )
    try:
        with pytest.raises(ValueError):
            _rename(conn, tenant_codes['old_code'], tenant_codes['new_code'], apply=True)
        cur.execute('SELECT code FROM tenant WHERE id = %s', (tenant_codes['old_id'],))
        assert cur.fetchone()[0] == tenant_codes['old_code']
    finally:
        cur.execute('DELETE FROM tenant WHERE id = %s', (target_id,))
