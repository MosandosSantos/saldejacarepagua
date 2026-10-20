"""Provisionamento atomico do tenant junto com seu Vale."""

from uuid import uuid4

import pytest
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.test import Client

from acesso.models import ROLE_ADMIN_SAAS, Tenant, Usuario
from contatos.models import Vale


pytestmark = pytest.mark.django_db(transaction=True)


def _cliente_admin_saas():
    suffix = uuid4().hex
    usuario = Usuario.objects.create(
        nome='Admin da plataforma',
        email=f'admin-{suffix}@example.test',
        senha=make_password('senha-de-teste'),
        role=ROLE_ADMIN_SAAS,
        tenant=None,
    )
    client = Client()
    session = client.session
    session['usuario_id'] = usuario.pk
    session['usuario'] = {
        'nome': usuario.nome,
        'email': usuario.email,
        'role': usuario.role,
        'tenant_id': None,
    }
    session.save()
    return client


def _post_vale(client, nome='Vale de teste', sigla='VDT'):
    return client.post('/contatos/prefeitura/nova/', {
        'nome': nome,
        'sigla': sigla,
    })


def test_admin_saas_without_context_creates_tenant_and_selects_it():
    client = _cliente_admin_saas()
    tenants_before = Tenant.objects.count()
    usuarios_before = Usuario.objects.count()

    response = _post_vale(client, nome='Vale Aurora', sigla='VAU')

    assert response.status_code == 302
    vale = Vale.objects.get(nome='Vale Aurora')
    assert vale.sigla == 'VAU'
    assert vale.tenant.nome == 'VAU'
    assert vale.tenant.slug == 'vau'
    assert client.session['admin_tenant_id'] == vale.tenant_id
    assert Tenant.objects.count() == tenants_before + 1
    assert Usuario.objects.count() == usuarios_before


def test_blank_sigla_is_rejected_without_creating_tenant():
    client = _cliente_admin_saas()
    tenants_before = Tenant.objects.count()

    response = _post_vale(client, nome='Vale sem sigla', sigla=' ')

    assert response.status_code == 200
    assert response.context['erro']
    assert Tenant.objects.count() == tenants_before
    assert not Vale.objects.filter(nome='Vale sem sigla').exists()


def test_sigla_that_normalizes_to_empty_is_rejected_without_orphan():
    client = _cliente_admin_saas()
    tenants_before = Tenant.objects.count()

    response = _post_vale(client, nome='Vale inválido', sigla='!!!')

    assert response.status_code == 200
    assert response.context['erro']
    assert Tenant.objects.count() == tenants_before
    assert not Vale.objects.filter(nome='Vale inválido').exists()


def test_overlength_sigla_is_rejected_without_creating_tenant():
    client = _cliente_admin_saas()
    tenants_before = Tenant.objects.count()

    response = _post_vale(client, nome='Vale com sigla longa', sigla='ABCDEFGHIJK')

    assert response.status_code == 200
    assert response.context['erro']
    assert Tenant.objects.count() == tenants_before
    assert not Vale.objects.filter(nome='Vale com sigla longa').exists()


def test_slug_collision_is_rejected_without_creating_orphan_tenant():
    Tenant.objects.create(nome='Tenant reservado', slug='vau')
    tenants_before = Tenant.objects.count()
    client = _cliente_admin_saas()

    response = _post_vale(client, nome='Outro Vale', sigla='VAU')

    assert response.status_code == 200
    assert response.context['erro']
    assert Tenant.objects.count() == tenants_before
    assert not Vale.objects.filter(nome='Outro Vale').exists()


def test_failure_saving_vale_rolls_back_new_tenant(monkeypatch):
    client = _cliente_admin_saas()
    tenants_before = Tenant.objects.count()

    def fail_vale_insert(**kwargs):
        raise IntegrityError('simulated Vale insert failure')

    monkeypatch.setattr(Vale.objects, 'create', fail_vale_insert)
    response = _post_vale(client, nome='Vale rollback', sigla='VRB')

    assert response.status_code == 200
    assert response.context['erro']
    assert Tenant.objects.count() == tenants_before
    assert not Tenant.objects.filter(slug='vrb').exists()


def test_tenant_can_be_linked_to_only_one_vale():
    tenant = Tenant.objects.create(nome='Tenant único', slug=f'unico-{uuid4().hex}')
    Vale.objects.create(tenant=tenant, nome='Vale primeiro', sigla='VP1')

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Vale.objects.create(tenant=tenant, nome='Vale segundo', sigla='VP2')


def test_editing_sigla_updates_tenant_name_without_changing_slug():
    tenant = Tenant.objects.create(nome='OLD', slug=f'old-{uuid4().hex}')
    original_slug = tenant.slug
    vale = Vale.objects.create(tenant=tenant, nome='Vale editável', sigla='OLD')
    client = _cliente_admin_saas()
    session = client.session
    session['admin_tenant_id'] = tenant.pk
    session.save()

    response = client.post(
        f'/contatos/prefeitura/{vale.pk}/editar/',
        {'nome': 'Vale editável', 'sigla': 'NEW'},
    )

    assert response.status_code == 302
    vale.refresh_from_db()
    tenant.refresh_from_db()
    assert vale.sigla == 'NEW'
    assert tenant.nome == 'NEW'
    assert tenant.slug == original_slug


def test_editing_to_an_existing_sigla_keeps_current_values():
    first_tenant = Tenant.objects.create(nome='SIG1', slug=f'sig1-{uuid4().hex}')
    second_tenant = Tenant.objects.create(nome='SIG2', slug=f'sig2-{uuid4().hex}')
    vale = Vale.objects.create(tenant=first_tenant, nome='Vale um', sigla='SIG1')
    Vale.objects.create(tenant=second_tenant, nome='Vale dois', sigla='SIG2')
    client = _cliente_admin_saas()
    session = client.session
    session['admin_tenant_id'] = first_tenant.pk
    session.save()

    response = client.post(
        f'/contatos/prefeitura/{vale.pk}/editar/',
        {'nome': 'Vale alterado', 'sigla': 'SIG2'},
    )

    assert response.status_code == 200
    assert response.context['erro']
    vale.refresh_from_db()
    first_tenant.refresh_from_db()
    assert vale.nome == 'Vale um'
    assert vale.sigla == 'SIG1'
    assert first_tenant.nome == 'SIG1'
