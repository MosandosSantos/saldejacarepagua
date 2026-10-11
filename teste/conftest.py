"""Configuracao dos testes — client HTTP, usuarios, tenants e headers de autenticacao."""
import os

import pytest

# Desliga o rate limiting da API nos testes (a suite faz centenas de requests).
# Precisa ser definido antes de qualquer request — leitura acontece no request.
os.environ['DJANGO_RATE_LIMIT'] = '0'

SENHA = 'senha123'


@pytest.fixture
def client():
    """Cliente HTTP contra a aplicacao FastAPI (usa o banco de teste do Django).

    Obs.: o TestClient roda o app numa thread propria; com `--reuse-db`
    (pytest.ini) o banco de teste persiste, evitando problemas de drop.
    """
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as test_client:
        yield test_client

    from django.db import connections

    connections.close_all()


@pytest.fixture
def tenant_aurora():
    from acesso.models import Tenant

    # get_or_create: a migracao 0002 do contatos semeia 'clinica-aurora' em
    # todo banco novo — criar de novo violaria o slug unico.
    tenant, _ = Tenant.objects.get_or_create(
        slug='clinica-aurora', defaults={'nome': 'Clínica Aurora'},
    )
    return tenant


@pytest.fixture
def tenant_beta():
    from acesso.models import Tenant

    tenant, _ = Tenant.objects.get_or_create(
        slug='clinica-beta', defaults={'nome': 'Clínica Beta'},
    )
    return tenant


def criar_usuario(nome, email, role, tenant):
    from django.contrib.auth.hashers import make_password

    from acesso.models import Usuario

    return Usuario.objects.create(
        nome=nome, email=email, role=role, tenant=tenant, senha=make_password(SENHA)
    )


@pytest.fixture
def usuario_operacional(tenant_aurora):
    return criar_usuario('Oper Aurora', 'oper@aurora.com', 'operacional', tenant_aurora)


@pytest.fixture
def usuario_operacional_beta(tenant_beta):
    return criar_usuario('Oper Beta', 'oper@beta.com', 'operacional', tenant_beta)


@pytest.fixture
def usuario_viewer(tenant_aurora):
    return criar_usuario('Laura Viewer', 'viewer@aurora.com', 'viewer', tenant_aurora)


@pytest.fixture
def admin_saas():
    return criar_usuario('Admin SaaS', 'admin@saas.com', 'admin_saas', None)


@pytest.fixture
def admin_company(tenant_aurora):
    return criar_usuario('Dona Aurora', 'dona@aurora.com', 'admin_company', tenant_aurora)


def fazer_login(client, email):
    resp = client.post('/api/v1/auth/login', json={'email': email, 'senha': SENHA})
    assert resp.status_code == 200
    return {'Authorization': f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def headers_operacional(client, usuario_operacional):
    return fazer_login(client, usuario_operacional.email)


@pytest.fixture
def headers_operacional_beta(client, usuario_operacional_beta):
    return fazer_login(client, usuario_operacional_beta.email)


@pytest.fixture
def headers_viewer(client, usuario_viewer):
    return fazer_login(client, usuario_viewer.email)


@pytest.fixture
def headers_admin_saas(client, admin_saas):
    return fazer_login(client, admin_saas.email)


@pytest.fixture
def headers_admin_company(client, admin_company):
    return fazer_login(client, admin_company.email)

# ---------------------------------------------------------------------------
# Banco GPRB de teste (specs/002-problema-pagamento)
# ---------------------------------------------------------------------------

def _resetar_conexao_gprb():
    """Fecha a conexão thread-local GPRB para reabrir com outro banco."""
    from core.gprb import connection as gconn

    antiga = getattr(gconn._tls, 'conn', None)
    if antiga is not None:
        try:
            antiga.close()
        except Exception:
            pass
    gconn._tls.conn = None


@pytest.fixture
def banco_gprb_teste(monkeypatch):
    """Aponta a camada GPRB (SQL cru) para `saldabritanea_test` durante o teste."""

    from core.gprb import connection as gconn
    from django.test import override_settings

    config_teste = _gprb_test_connection_settings()
    if config_teste is None:
        pytest.skip('GPRB integration tests require a local/Compose test PostgreSQL')

    codigo_override = override_settings(
        GPRB_TENANT_CODE='GPRB', GPRB_DB_ENABLED=True,
    )
    codigo_override.enable()
    for chave, valor in config_teste.items():
        monkeypatch.setenv(chave, valor)
    _resetar_conexao_gprb()
    try:
        conn = gconn.connect()
        if isinstance(conn, gconn._DummyConnection):
            pytest.skip('Local GPRB test database is unavailable')
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT to_regclass('public.tenant'), to_regclass('public.member')"
                )
                tabelas = cur.fetchone()
        except gconn.psycopg.Error:
            pytest.skip('Local GPRB test database is unavailable')
        finally:
            conn.close()
        if not tabelas or any(tabela is None for tabela in tabelas):
            pytest.skip('Local GPRB test schema is unavailable')
        yield
    finally:
        _resetar_conexao_gprb()
        codigo_override.disable()


def _gprb_test_connection_settings():
    """Require explicit test-only GPRB settings for a local/Compose endpoint."""
    host = (os.environ.get('GPRB_TEST_DB_HOST') or '').strip()
    port = (os.environ.get('GPRB_TEST_DB_PORT') or '').strip()
    user = (os.environ.get('GPRB_TEST_DB_USER') or '').strip()
    if host not in {'localhost', '127.0.0.1', '::1', 'db'} or not port.isdigit() or not user:
        return None
    if 'GPRB_TEST_DB_PASSWORD' not in os.environ:
        return None
    return {
        'GPRB_DB_HOST': host,
        'GPRB_DB_PORT': port,
        'GPRB_DB_NAME': 'saldabritanea_test',
        'GPRB_DB_USER': user,
        'GPRB_DB_PASSWORD': os.environ['GPRB_TEST_DB_PASSWORD'],
        'GPRB_DB_SSLMODE': 'disable',
        'GPRB_DB_TIMEOUT': '3',
    }
