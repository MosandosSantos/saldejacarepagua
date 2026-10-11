"""Rendered form contract for Vale Secretaria and Tesouraria contacts."""

import re
from uuid import uuid4

import pytest
from django.test import Client

from acesso.models import ROLE_GRANDE_PRIOR, Tenant, Usuario
from contatos.models import Vale


def _client_for_tenant(tenant):
    suffix = uuid4().hex
    user = Usuario.objects.create(
        nome='Editor de Vale',
        email=f'editor-{suffix}@example.test',
        senha='!',
        role=ROLE_GRANDE_PRIOR,
        tenant=tenant,
    )
    client = Client()
    session = client.session
    session['usuario_id'] = user.pk
    session['usuario'] = {
        'nome': user.nome,
        'email': user.email,
        'role': user.role,
        'tenant_id': tenant.pk,
    }
    session.save()
    return client


@pytest.mark.django_db(transaction=True)
def test_create_and_edit_show_both_contact_groups():
    tenant = Tenant.objects.create(
        nome='Tenant dos contatos', slug=f'vale-templates-{uuid4().hex}',
    )
    client = _client_for_tenant(tenant)
    create_html = client.get('/contatos/prefeitura/nova/').content.decode()

    contact_fields = {
        'secretario_nome': 'Nome do Secretário',
        'secretario_email': 'E-mail do Secretário',
        'secretario_telefone': 'Telefone do Secretário',
        'tesoureiro_nome': 'Nome do Tesoureiro',
        'tesoureiro_email': 'E-mail do Tesoureiro',
        'tesoureiro_telefone': 'Telefone do Tesoureiro',
    }
    for field, label in contact_fields.items():
        assert f'name="{field}"' in create_html
        assert label in create_html
        input_tag = re.search(rf'<input\b[^>]*name="{field}"[^>]*>', create_html)
        assert input_tag is not None
        assert ' required' not in input_tag.group(0)

    for field in ('secretario_email', 'tesoureiro_email'):
        input_tag = re.search(rf'<input\b[^>]*name="{field}"[^>]*>', create_html)
        assert 'value=' not in input_tag.group(0)

    vale = Vale.objects.create(
        tenant=tenant,
        nome='Vale com contatos',
        secretario_nome='Secretário salvo',
        secretario_email='farelli@gprbr',
        secretario_telefone='(21) 99999-9999',
        tesoureiro_nome='Tesoureiro salvo',
        tesoureiro_email='tesouraria@potencia.com',
        tesoureiro_telefone='(21) 98888-9999',
    )
    edit_html = client.get(f'/contatos/prefeitura/{vale.pk}/editar/').content.decode()

    for value in (
        'Secretário salvo',
        'farelli@gprbr',
        '(21) 99999-9999',
        'Tesoureiro salvo',
        'tesouraria@potencia.com',
        '(21) 98888-9999',
    ):
        assert f'value="{value}"' in edit_html


@pytest.mark.django_db(transaction=True)
def test_consult_lists_complete_contact_details_without_gprb_counts():
    tenant = Tenant.objects.create(
        nome='Tenant consulta', slug=f'vale-lista-{uuid4().hex}',
    )
    vale = Vale.objects.create(
        tenant=tenant,
        nome='Vale da consulta',
        secretario_nome='Secretário da consulta',
        secretario_email='secretario@gprbr',
        secretario_telefone='(21) 90000-0001',
        tesoureiro_nome='Tesoureira da consulta',
        tesoureiro_email='tesouraria@gprbr',
        tesoureiro_telefone='(21) 90000-0002',
    )
    client = _client_for_tenant(tenant)

    response = client.get('/contatos/prefeituras/')
    html = response.content.decode()

    assert response.status_code == 200
    for value in (
        vale.nome,
        'Secretário da consulta',
        'secretario@gprbr',
        '(21) 90000-0001',
        'Tesoureira da consulta',
        'tesouraria@gprbr',
        '(21) 90000-0002',
    ):
        assert value in html
    assert 'Total de lojas' not in html
    assert 'Total de membros' not in html
    assert 'Expandir lojas' not in html
    assert 'lojas-json' not in html


@pytest.mark.django_db(transaction=True)
def test_delete_confirmation_lists_complete_contact_details_without_external_guard():
    tenant = Tenant.objects.create(
        nome='Tenant exclusão', slug=f'vale-exclusao-{uuid4().hex}',
    )
    vale = Vale.objects.create(
        tenant=tenant,
        nome='Vale para excluir',
        secretario_nome='Secretária da exclusão',
        secretario_email='secretaria@gprbr',
        secretario_telefone='(21) 91111-0001',
        tesoureiro_nome='Tesoureiro da exclusão',
        tesoureiro_email='tesouraria@gprbr',
        tesoureiro_telefone='(21) 91111-0002',
    )
    client = _client_for_tenant(tenant)

    response = client.get(f'/contatos/prefeitura/{vale.pk}/excluir/')
    html = response.content.decode()

    assert response.status_code == 200
    for value in (
        vale.nome,
        'Secretária da exclusão',
        'secretaria@gprbr',
        '(21) 91111-0001',
        'Tesoureiro da exclusão',
        'tesouraria@gprbr',
        '(21) 91111-0002',
    ):
        assert value in html
    assert 'possui lojas vinculadas' not in html
    assert 'nao pode ser excluido' not in html
    assert 'Confirmar Exclusao' in html
