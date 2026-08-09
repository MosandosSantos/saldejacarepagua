"""Testes de RBAC — quem pode criar usuarios/tenants e regras de tenant."""
import pytest


@pytest.mark.django_db(transaction=True)
def test_admin_saas_cria_admin_company(client, tenant_aurora, headers_admin_saas):
    resp = client.post('/api/v1/usuarios', headers=headers_admin_saas, json={
        'nome': 'Dona Aurora',
        'email': 'dona@aurora.com',
        'senha': 'senha123',
        'role': 'admin_company',
        'tenant_id': tenant_aurora.id,
    })

    assert resp.status_code == 201
    dados = resp.json()
    assert dados['role'] == 'admin_company'
    assert dados['tenant_id'] == tenant_aurora.id
    assert 'senha' not in dados


@pytest.mark.django_db(transaction=True)
def test_admin_saas_cria_operacional(client, tenant_aurora, headers_admin_saas):
    resp = client.post('/api/v1/usuarios', headers=headers_admin_saas, json={
        'nome': 'Ana Souza',
        'email': 'ana@aurora.com',
        'senha': 'senha123',
        'role': 'operacional',
        'tenant_id': tenant_aurora.id,
    })

    assert resp.status_code == 201


@pytest.mark.django_db(transaction=True)
def test_admin_company_nao_cria_usuario(client, headers_admin_company):
    resp = client.post('/api/v1/usuarios', headers=headers_admin_company, json={
        'nome': 'Carlos X', 'email': 'x@aurora.com', 'senha': 'senha123', 'role': 'operacional',
        'tenant_id': 1,
    })

    assert resp.status_code == 403


@pytest.mark.django_db(transaction=True)
def test_operacional_nao_cria_usuario(client, headers_operacional):
    resp = client.post('/api/v1/usuarios', headers=headers_operacional, json={
        'nome': 'Carlos X', 'email': 'x@aurora.com', 'senha': 'senha123', 'role': 'operacional',
        'tenant_id': 1,
    })

    assert resp.status_code == 403


@pytest.mark.django_db(transaction=True)
def test_criar_usuario_sem_token(client):
    resp = client.post('/api/v1/usuarios', json={
        'nome': 'Carlos X', 'email': 'x@aurora.com', 'senha': 'senha123', 'role': 'operacional',
    })

    assert resp.status_code == 401


@pytest.mark.django_db(transaction=True)
def test_admin_company_sem_tenant_rejeitado(client, headers_admin_saas):
    resp = client.post('/api/v1/usuarios', headers=headers_admin_saas, json={
        'nome': 'Carlos X', 'email': 'x@aurora.com', 'senha': 'senha123', 'role': 'admin_company',
    })

    assert resp.status_code == 409


@pytest.mark.django_db(transaction=True)
def test_operacional_sem_tenant_rejeitado(client, headers_admin_saas):
    resp = client.post('/api/v1/usuarios', headers=headers_admin_saas, json={
        'nome': 'Carlos X', 'email': 'x@aurora.com', 'senha': 'senha123', 'role': 'operacional',
    })

    assert resp.status_code == 409


@pytest.mark.django_db(transaction=True)
def test_admin_saas_com_tenant_rejeitado(client, tenant_aurora, headers_admin_saas):
    resp = client.post('/api/v1/usuarios', headers=headers_admin_saas, json={
        'nome': 'Carlos X', 'email': 'x@saas.com', 'senha': 'senha123', 'role': 'admin_saas',
        'tenant_id': tenant_aurora.id,
    })

    assert resp.status_code == 409


@pytest.mark.django_db(transaction=True)
def test_tenant_inexistente_rejeitado(client, headers_admin_saas):
    resp = client.post('/api/v1/usuarios', headers=headers_admin_saas, json={
        'nome': 'Carlos X', 'email': 'x@aurora.com', 'senha': 'senha123', 'role': 'operacional',
        'tenant_id': 99999,
    })

    assert resp.status_code == 409


@pytest.mark.django_db(transaction=True)
def test_email_duplicado_rejeitado(client, usuario_operacional, tenant_aurora, headers_admin_saas):
    resp = client.post('/api/v1/usuarios', headers=headers_admin_saas, json={
        'nome': 'Outro',
        'email': 'oper@aurora.com',
        'senha': 'senha123',
        'role': 'operacional',
        'tenant_id': tenant_aurora.id,
    })

    assert resp.status_code == 409


@pytest.mark.django_db(transaction=True)
def test_senha_curta_rejeitada(client, tenant_aurora, headers_admin_saas):
    resp = client.post('/api/v1/usuarios', headers=headers_admin_saas, json={
        'nome': 'Carlos X', 'email': 'x@aurora.com', 'senha': 'curta', 'role': 'operacional',
        'tenant_id': tenant_aurora.id,
    })

    assert resp.status_code == 422


@pytest.mark.django_db(transaction=True)
def test_role_invalida_rejeitada(client, tenant_aurora, headers_admin_saas):
    resp = client.post('/api/v1/usuarios', headers=headers_admin_saas, json={
        'nome': 'Carlos X', 'email': 'x@aurora.com', 'senha': 'senha123', 'role': 'hacker',
        'tenant_id': tenant_aurora.id,
    })

    assert resp.status_code == 422


@pytest.mark.django_db(transaction=True)
def test_admin_saas_cria_tenant(client, headers_admin_saas):
    resp = client.post('/api/v1/tenants', headers=headers_admin_saas, json={
        'nome': 'Clínica Beta', 'slug': 'clinica-beta',
    })

    assert resp.status_code == 201
    assert resp.json()['slug'] == 'clinica-beta'


@pytest.mark.django_db(transaction=True)
def test_slug_duplicado_rejeitado(client, tenant_aurora, headers_admin_saas):
    resp = client.post('/api/v1/tenants', headers=headers_admin_saas, json={
        'nome': 'Outra', 'slug': 'clinica-aurora',
    })

    assert resp.status_code == 409


@pytest.mark.django_db(transaction=True)
def test_slug_invalido_rejeitado(client, headers_admin_saas):
    resp = client.post('/api/v1/tenants', headers=headers_admin_saas, json={
        'nome': 'Clínica Beta', 'slug': 'Clinica Beta',
    })

    assert resp.status_code == 422


@pytest.mark.django_db(transaction=True)
def test_admin_company_nao_lista_tenants(client, headers_admin_company):
    resp = client.get('/api/v1/tenants', headers=headers_admin_company)

    assert resp.status_code == 403
