"""Web CRUD tests for local Vales; the external GPRB connector is forbidden."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client

from acesso.models import ROLE_ADMIN_SAAS, ROLE_GRANDE_PRIOR, ROLE_VIEWER, Tenant, Usuario
from contatos.models import Vale
from core.gprb import connection as gprb_connection


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


def _usuario(tenant, role=ROLE_GRANDE_PRIOR):
    suffix = uuid4().hex
    return Usuario.objects.create(
        nome='Usuário de teste',
        email=f'vale-{suffix}@example.test',
        senha=make_password('senha-de-teste'),
        role=role,
        tenant=tenant,
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


def _dados(nome='Vale teste'):
    return {
        'nome': nome,
        'sigla': 'VT',
        'prefeito': 'Delegado de teste',
        'telefone': '(21) 90000-0000',
        'email': 'delegado@gprbr',
        'secretario_nome': 'Secretário de teste',
        'secretario_email': 'farelli@gprbr',
        'secretario_telefone': '(21) 99999-9999',
        'tesoureiro_nome': 'Tesoureiro de teste',
        'tesoureiro_email': 'tesouraria@potencia.com',
        'tesoureiro_telefone': '(21) 98888-9999',
        'valor_anuidade': '1.500,00',
        'vencimento_anuidade': '2027-01-31',
        'pix': 'pix-vale-teste',
    }


def test_create_vale_persists_all_contact_fields():
    tenant = _tenant()
    client = _cliente(_usuario(tenant))

    response = client.post('/contatos/prefeitura/nova/', _dados())

    assert response.status_code == 302
    vale = Vale.objects.get(tenant=tenant, nome='Vale teste')
    assert vale.secretario_nome == 'Secretário de teste'
    assert vale.secretario_email == 'farelli@gprbr'
    assert vale.secretario_telefone == '(21) 99999-9999'
    assert vale.tesoureiro_nome == 'Tesoureiro de teste'
    assert vale.tesoureiro_email == 'tesouraria@potencia.com'
    assert vale.tesoureiro_telefone == '(21) 98888-9999'
    assert vale.valor_anuidade == Decimal('1500.00')
    assert vale.vencimento_anuidade == date(2027, 1, 31)


def test_edit_vale_updates_contacts():
    tenant = _tenant()
    vale = Vale.objects.create(tenant=tenant, nome='Vale editado')
    client = _cliente(_usuario(tenant))
    dados = _dados('Vale editado')
    dados['secretario_nome'] = 'Secretária alterada'
    dados['tesoureiro_nome'] = 'Tesoureiro alterado'

    response = client.post(f'/contatos/prefeitura/{vale.pk}/editar/', dados)

    assert response.status_code == 302
    vale.refresh_from_db()
    assert vale.secretario_nome == 'Secretária alterada'
    assert vale.tesoureiro_nome == 'Tesoureiro alterado'
    assert vale.secretario_email == 'farelli@gprbr'


def test_edit_preserves_blank_delegate_fields_instead_of_saving_display_dash():
    tenant = _tenant()
    vale = Vale.objects.create(tenant=tenant, nome='Vale sem Delegado')
    client = _cliente(_usuario(tenant))
    edit_page = client.get(f'/contatos/prefeitura/{vale.pk}/editar/')
    form_value = edit_page.context['prefeitura']
    dados = _dados('Vale sem Delegado')
    dados['prefeito'] = form_value['prefeito']
    dados['telefone'] = form_value['telefone']

    response = client.post(f'/contatos/prefeitura/{vale.pk}/editar/', dados)

    assert response.status_code == 302
    vale.refresh_from_db()
    assert vale.prefeito == ''
    assert vale.telefone == ''


def test_list_vales_is_tenant_scoped():
    tenant = _tenant()
    other_tenant = _tenant()
    Vale.objects.create(tenant=tenant, nome='Vale visível')
    Vale.objects.create(tenant=other_tenant, nome='Vale de outro tenant')
    client = _cliente(_usuario(tenant))

    response = client.get('/contatos/prefeituras/')
    html = response.content.decode()

    assert response.status_code == 200
    assert 'Vale visível' in html
    assert 'Vale de outro tenant' not in html


def test_admin_saas_without_tenant_can_list_all_vales():
    first = _tenant()
    second = _tenant()
    Vale.objects.create(tenant=first, nome='Vale tenant um')
    Vale.objects.create(tenant=second, nome='Vale tenant dois')
    client = _cliente(_usuario(None, ROLE_ADMIN_SAAS))

    response = client.get('/contatos/prefeituras/')
    html = response.content.decode()

    assert response.status_code == 200
    assert 'Vale tenant um' in html
    assert 'Vale tenant dois' in html


def test_unselected_admin_saas_cannot_create_vale():
    client = _cliente(_usuario(None, ROLE_ADMIN_SAAS))
    vales_before = Vale.objects.count()

    response = client.post('/contatos/prefeitura/nova/', _dados('Sem tenant'))

    assert response.status_code == 403
    assert Vale.objects.count() == vales_before


def test_unselected_admin_saas_cannot_edit_vale():
    tenant = _tenant()
    vale = Vale.objects.create(tenant=tenant, nome='Vale protegido')
    client = _cliente(_usuario(None, ROLE_ADMIN_SAAS))

    response = client.post(
        f'/contatos/prefeitura/{vale.pk}/editar/',
        _dados('Nome indevido'),
    )

    vale.refresh_from_db()
    assert response.status_code == 403
    assert vale.nome == 'Vale protegido'


def test_unselected_admin_saas_cannot_delete_vale():
    tenant = _tenant()
    vale = Vale.objects.create(tenant=tenant, nome='Vale protegido')
    client = _cliente(_usuario(None, ROLE_ADMIN_SAAS))

    response = client.post(f'/contatos/prefeitura/{vale.pk}/excluir/')

    assert response.status_code == 403
    assert Vale.objects.filter(pk=vale.pk, tenant=tenant).exists()


def test_tenantless_non_saas_cannot_list_vales():
    client = _cliente(_usuario(None, ROLE_VIEWER))

    response = client.get('/contatos/prefeituras/')

    assert response.status_code == 403


def test_delete_vale_deletes_only_local_record():
    tenant = _tenant()
    vale = Vale.objects.create(
        tenant=tenant,
        nome='Vale para excluir',
        secretario_nome='Secretária',
        secretario_email='farelli@gprbr',
        tesoureiro_nome='Tesoureiro',
    )
    client = _cliente(_usuario(tenant))

    confirmation = client.get(f'/contatos/prefeitura/{vale.pk}/excluir/')
    assert confirmation.status_code == 200

    response = client.post(f'/contatos/prefeitura/{vale.pk}/excluir/')

    assert response.status_code == 302
    assert not Vale.objects.filter(tenant=tenant, pk=vale.pk).exists()
