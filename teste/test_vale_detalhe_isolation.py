"""Tenant isolation for the Vale detail view; the external GPRB connector is forbidden."""

from uuid import uuid4

import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client

from acesso.models import ROLE_ADMIN_SAAS, ROLE_VIEWER, Tenant, Usuario
from contatos.models import Vale


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def external_gprb_must_not_be_used(monkeypatch):
    from repositories import gprb_repository

    monkeypatch.setattr(
        gprb_repository,
        'connect',
        lambda: pytest.fail('local Vale CRUD must not connect to GPRB'),
    )


def _tenant():
    suffix = uuid4().hex
    return Tenant.objects.create(nome=f'Vale tenant {suffix}', slug=f'vale-{suffix}')


def _usuario(tenant, role=ROLE_VIEWER):
    suffix = uuid4().hex
    return Usuario.objects.create(
        nome=f'Vale user {suffix}',
        email=f'vale-{suffix}@example.com',
        senha=make_password('senha123'),
        role=role,
        tenant=tenant,
    )


def _vale(tenant, nome, status='ATIVA'):
    return Vale.objects.create(
        tenant=tenant,
        nome=nome,
        sigla=f'V{uuid4().hex[:6].upper()}',
        status=status,
    )


def _cliente(usuario):
    client = Client()
    session = client.session
    session['usuario_id'] = usuario.pk
    session['usuario'] = {
        'nome': usuario.nome,
        'email': usuario.email,
        'role': usuario.role,
        'tenant_id': usuario.tenant_id,
    }
    session.save()
    return client


def test_tenant_user_sees_own_vale_detail():
    tenant = _tenant()
    vale = _vale(tenant, 'Vale visivel do proprio tenant')
    client = _cliente(_usuario(tenant))

    response = client.get(f'/contatos/prefeitura/{vale.pk}/')

    assert response.status_code == 200
    assert 'Vale visivel do proprio tenant' in response.content.decode()


def test_tenant_user_cannot_see_other_tenant_vale_detail():
    tenant = _tenant()
    other_tenant = _tenant()
    _vale(tenant, 'Vale do proprio tenant')
    other_vale = _vale(other_tenant, 'Vale de outro tenant')
    client = _cliente(_usuario(tenant))

    response = client.get(f'/contatos/prefeitura/{other_vale.pk}/')

    assert response.status_code == 404
    assert 'Vale de outro tenant' not in response.content.decode()


def test_tenantless_non_saas_cannot_open_vale_detail():
    tenant = _tenant()
    vale = _vale(tenant, 'Vale de outro tenant')
    client = _cliente(_usuario(None, ROLE_VIEWER))

    response = client.get(f'/contatos/prefeitura/{vale.pk}/')

    assert response.status_code == 403
    assert 'Vale de outro tenant' not in response.content.decode()


def test_admin_saas_without_tenant_can_open_any_active_vale():
    tenant = _tenant()
    vale = _vale(tenant, 'Vale visivel para admin saas')
    client = _cliente(_usuario(None, ROLE_ADMIN_SAAS))

    response = client.get(f'/contatos/prefeitura/{vale.pk}/')

    assert response.status_code == 200
    assert 'Vale visivel para admin saas' in response.content.decode()


def test_inactive_vale_detail_returns_404():
    tenant = _tenant()
    inactive = _vale(tenant, 'Vale inativo', status='INATIVA')
    client = _cliente(_usuario(None, ROLE_ADMIN_SAAS))

    response = client.get(f'/contatos/prefeitura/{inactive.pk}/')

    assert response.status_code == 404
    assert 'Vale inativo' not in response.content.decode()


def test_unknown_vale_detail_returns_404():
    tenant = _tenant()
    _vale(tenant, 'Vale do proprio tenant')
    client = _cliente(_usuario(tenant))

    response = client.get('/contatos/prefeitura/99999999/')

    assert response.status_code == 404
