"""Arquivamento preserva o tenant e as contas vinculadas ao Vale."""

from uuid import uuid4

import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client

from acesso.models import ROLE_ADMIN_SAAS, ROLE_DELEGADO, Tenant, Usuario
from contatos.models import Vale


pytestmark = pytest.mark.django_db(transaction=True)


def _tenant_com_vale():
    suffix = uuid4().hex
    tenant = Tenant.objects.create(nome=f'VA-{suffix[:6]}', slug=f'va-{suffix}')
    vale = Vale.objects.create(
        tenant=tenant,
        nome=f'Vale {suffix[:6]}',
        sigla=f'V{suffix[:6]}',
    )
    return tenant, vale


def _usuario(tenant, role):
    suffix = uuid4().hex
    return Usuario.objects.create(
        nome='Usuário do Vale',
        email=f'vale-{suffix}@example.test',
        senha=make_password('senha-de-teste'),
        role=role,
        tenant=tenant,
    )


def _cliente(usuario, selected_tenant_id=None):
    client = Client()
    session = client.session
    session['usuario_id'] = usuario.pk
    session['usuario'] = {
        'nome': usuario.nome,
        'email': usuario.email,
        'role': usuario.role,
        'tenant_id': usuario.tenant_id,
    }
    if selected_tenant_id is not None:
        session['admin_tenant_id'] = selected_tenant_id
    session.save()
    return client


def test_archiving_vale_preserves_tenant_and_user():
    tenant, vale = _tenant_com_vale()
    admin = _usuario(None, ROLE_ADMIN_SAAS)
    user = _usuario(tenant, ROLE_DELEGADO)
    client = _cliente(admin, tenant.pk)

    response = client.post(f'/contatos/prefeitura/{vale.pk}/excluir/')

    assert response.status_code == 302
    vale.refresh_from_db()
    assert vale.status == 'INATIVA'
    assert Tenant.objects.filter(pk=tenant.pk).exists()
    assert Usuario.objects.filter(pk=user.pk, tenant=tenant).exists()


def test_archived_vale_blocks_common_user_routes():
    tenant, vale = _tenant_com_vale()
    vale.status = 'INATIVA'
    vale.save(update_fields=['status'])
    user = _usuario(tenant, ROLE_DELEGADO)
    client = _cliente(user)

    response = client.get('/contatos/prefeituras/')

    assert response.status_code == 403
    assert Vale.objects.filter(pk=vale.pk, status='INATIVA').exists()


def test_archived_vale_is_hidden_from_admin_tenant_selector_but_regular_tenant_remains():
    archived_tenant, archived_vale = _tenant_com_vale()
    archived_vale.status = 'INATIVA'
    archived_vale.save(update_fields=['status'])
    regular_tenant = Tenant.objects.create(
        nome='Tenant sem Vale',
        slug=f'sem-vale-{uuid4().hex}',
    )
    admin = _usuario(None, ROLE_ADMIN_SAAS)
    client = _cliente(admin)

    response = client.get('/contatos/prefeituras/')

    assert response.status_code == 200
    option_ids = {tenant.pk for tenant in response.context['web_tenant_options']}
    assert archived_tenant.pk not in option_ids
    assert regular_tenant.pk in option_ids


def test_admin_saas_can_reactivate_archived_vale_without_selected_tenant():
    tenant, vale = _tenant_com_vale()
    vale.status = 'INATIVA'
    vale.save(update_fields=['status'])
    admin = _usuario(None, ROLE_ADMIN_SAAS)
    client = _cliente(admin)

    response = client.post(f'/contatos/prefeitura/{vale.pk}/reativar/')

    assert response.status_code == 302
    vale.refresh_from_db()
    assert vale.status == 'ATIVA'
    assert Tenant.objects.filter(pk=tenant.pk).exists()
