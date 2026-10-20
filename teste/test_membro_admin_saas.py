"""Testes de acesso global do Admin SaaS e isolamento de tenant para membros."""

from datetime import date
from uuid import uuid4

import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client

from acesso.models import ROLE_ADMIN_SAAS, ROLE_ADM, ROLE_DELEGADO, Tenant, Usuario
from contatos.models import Loja, Membro, Vale


pytestmark = pytest.mark.django_db(transaction=True)


def _usuario(role, tenant=None):
    """Cria usuário com o papel e tenant especificados."""
    suffix = uuid4().hex
    return Usuario.objects.create(
        nome='Teste',
        email=f'user-{suffix}@test.com',
        senha=make_password('senha123'),
        role=role,
        tenant=tenant,
    )


def _cliente(usuario):
    """Cria cliente autenticado com o usuário."""
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


def _tenant_com_vale(nome='Vale Teste'):
    """Cria tenant com Vale ativo."""
    suffix = uuid4().hex
    tenant = Tenant.objects.create(
        nome=f'{nome} {suffix}',
        slug=f'{nome.lower()}-{suffix}',
    )
    vale = Vale.objects.create(
        tenant=tenant,
        nome=nome,
        sigla=f'VL{suffix[:6].upper()}',
        status='ATIVA',
    )
    return tenant, vale


def _tenant_sem_vale(nome='Tenant Sem Vale'):
    """Cria tenant sem Vale."""
    suffix = uuid4().hex
    return Tenant.objects.create(
        nome=f'{nome} {suffix}',
        slug=f'{nome.lower()}-{suffix}',
    )


def _tenant_com_vale_arquivado(nome='Vale Arquivado'):
    """Cria tenant com Vale arquivado."""
    suffix = uuid4().hex
    tenant = Tenant.objects.create(
        nome=f'{nome} {suffix}',
        slug=f'{nome.lower()}-{suffix}',
    )
    Vale.objects.create(
        tenant=tenant,
        nome=nome,
        sigla=f'VA{suffix[:6].upper()}',
        status='INATIVA',
    )
    return tenant


def test_admin_saas_without_selection_lists_members_from_multiple_tenants():
    """Admin SaaS sem seleção deve listar membros de múltiplos tenants."""
    tenant1, _ = _tenant_com_vale('Vale 1')
    tenant2, _ = _tenant_com_vale('Vale 2')

    Membro.objects.create(tenant=tenant1, nome='Membro Tenant 1', cpf='11111111111', situacao='ATIVO')
    Membro.objects.create(tenant=tenant2, nome='Membro Tenant 2', cpf='22222222222', situacao='ATIVO')

    admin = _usuario(ROLE_ADMIN_SAAS, tenant=None)
    client = _cliente(admin)

    response = client.get('/membros/')
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Membro Tenant 1' in content
    assert 'Membro Tenant 2' in content


def test_admin_saas_without_selection_opens_member_in_another_tenant():
    """Admin SaaS sem seleção abre membro de outro tenant."""
    tenant1, _ = _tenant_com_vale('Vale 1')
    tenant2, _ = _tenant_com_vale('Vale 2')

    membro = Membro.objects.create(tenant=tenant2, nome='Membro Tenant 2', cpf='33333333333', situacao='ATIVO')

    admin = _usuario(ROLE_ADMIN_SAAS, tenant=None)
    client = _cliente(admin)

    response = client.get(f'/membros/{membro.pk}/')
    assert response.status_code == 200
    assert 'Membro Tenant 2' in response.content.decode()


def test_admin_saas_selected_header_context_still_lists_members_globally():
    """Admin SaaS com tenant selecionado no header ainda lista globalmente."""
    tenant1, _ = _tenant_com_vale('Vale 1')
    tenant2, _ = _tenant_com_vale('Vale 2')

    Membro.objects.create(tenant=tenant1, nome='Membro Tenant 1', cpf='11111111111', situacao='ATIVO')
    Membro.objects.create(tenant=tenant2, nome='Membro Tenant 2', cpf='22222222222', situacao='ATIVO')

    admin = _usuario(ROLE_ADMIN_SAAS, tenant=None)
    client = _cliente(admin)
    client.session['admin_tenant_id'] = tenant1.pk
    client.session.save()

    response = client.get('/membros/')
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Membro Tenant 1' in content
    assert 'Membro Tenant 2' in content


def test_admin_saas_can_read_member_of_archived_or_no_vale_tenant():
    """Admin SaaS pode ler membro de tenant sem Vale ou com Vale arquivado."""
    tenant_sem_vale = _tenant_sem_vale()
    tenant_arquivado = _tenant_com_vale_arquivado()

    membro_sem_vale = Membro.objects.create(tenant=tenant_sem_vale, nome='Sem Vale', cpf='11111111111', situacao='ATIVO')
    membro_arquivado = Membro.objects.create(tenant=tenant_arquivado, nome='Arquivado', cpf='22222222222', situacao='ATIVO')

    admin = _usuario(ROLE_ADMIN_SAAS, tenant=None)
    client = _cliente(admin)

    response_sem = client.get(f'/membros/{membro_sem_vale.pk}/')
    assert response_sem.status_code == 200
    assert 'Sem Vale' in response_sem.content.decode()

    response_arq = client.get(f'/membros/{membro_arquivado.pk}/')
    assert response_arq.status_code == 200
    assert 'Arquivado' in response_arq.content.decode()


def test_adm_member_list_and_detail_are_scoped_to_account_tenant():
    """ADM só vê membros do próprio tenant."""
    tenant1, _ = _tenant_com_vale('Vale 1')
    tenant2, _ = _tenant_com_vale('Vale 2')

    Membro.objects.create(tenant=tenant1, nome='Membro Tenant 1', cpf='11111111111', situacao='ATIVO')
    Membro.objects.create(tenant=tenant2, nome='Membro Tenant 2', cpf='22222222222', situacao='ATIVO')

    adm = _usuario(ROLE_ADM, tenant=tenant1)
    client = _cliente(adm)

    response = client.get('/membros/')
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Membro Tenant 1' in content
    assert 'Membro Tenant 2' not in content

    # Tenta acessar membro do outro tenant
    membro2 = Membro.objects.get(tenant=tenant2)
    response = client.get(f'/membros/{membro2.pk}/')
    assert response.status_code == 404


def test_adm_cannot_access_members_when_its_vale_is_archived():
    """ADM não acessa membros quando seu Vale está arquivado."""
    tenant = _tenant_com_vale_arquivado()
    Membro.objects.create(tenant=tenant, nome='Membro Arquivado', cpf='11111111111', situacao='ATIVO')

    adm = _usuario(ROLE_ADM, tenant=tenant)
    client = _cliente(adm)

    response = client.get('/membros/')
    assert response.status_code == 403


def test_tenant_user_cannot_open_foreign_member():
    """Usuário de tenant não abre membro de outro tenant."""
    tenant1, _ = _tenant_com_vale('Vale 1')
    tenant2, _ = _tenant_com_vale('Vale 2')

    membro = Membro.objects.create(tenant=tenant2, nome='Membro Tenant 2', cpf='33333333333', situacao='ATIVO')

    usuario = _usuario(ROLE_DELEGADO, tenant=tenant1)
    client = _cliente(usuario)

    response = client.get(f'/membros/{membro.pk}/')
    assert response.status_code == 404