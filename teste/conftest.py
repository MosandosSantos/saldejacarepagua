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
    from api.main import app
    from fastapi.testclient import TestClient

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
    from acesso.models import Usuario
    from django.contrib.auth.hashers import make_password

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
