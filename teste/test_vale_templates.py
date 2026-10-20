"""Rendered form contract for Vale Secretaria and Tesouraria contacts."""

import re
from uuid import uuid4

import pytest
from django.test import Client

from acesso.models import ROLE_ADM, ROLE_DELEGADO, Tenant, Usuario
from contatos.models import Loja, Membro, Vale


def _client_for_tenant(tenant, role=ROLE_DELEGADO):
    suffix = uuid4().hex
    user = Usuario.objects.create(
        nome='Editor de Vale',
        email=f'editor-{suffix}@example.test',
        senha='!',
        role=role,
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


def _client_admin_saas():
    suffix = uuid4().hex
    user = Usuario.objects.create(
        nome='Admin SaaS',
        email=f'admin-saas-{suffix}@example.test',
        senha='!',
        role='admin_saas',
        tenant=None,
    )
    client = Client()
    session = client.session
    session['usuario_id'] = user.pk
    session['usuario'] = {
        'nome': user.nome,
        'email': user.email,
        'role': user.role,
        'tenant_id': None,
    }
    session.save()
    return client


@pytest.mark.django_db(transaction=True)
def test_create_and_edit_show_both_contact_groups():
    client = _client_admin_saas()
    create_html = client.get('/contatos/prefeitura/nova/').content.decode()
    assert 'name="sigla"' in create_html
    sigla_input = re.search(r'<input\b[^>]*name="sigla"[^>]*>', create_html)
    assert sigla_input is not None
    assert ' required' in sigla_input.group(0)

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

    tenant = Tenant.objects.create(
        nome='VCT', slug=f'vale-templates-{uuid4().hex}',
    )
    vale = Vale.objects.create(
        tenant=tenant,
        nome='Vale com contatos',
        sigla='VCT',
        secretario_nome='Secretário salvo',
        secretario_email='farelli@gprbr',
        secretario_telefone='(21) 99999-9999',
        tesoureiro_nome='Tesoureiro salvo',
        tesoureiro_email='tesouraria@potencia.com',
        tesoureiro_telefone='(21) 98888-9999',
    )
    session = client.session
    session['admin_tenant_id'] = tenant.pk
    session.save()
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
        sigla='VCL',
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
    assert '<details' not in html
    assert 'lojas-json' not in html


@pytest.mark.django_db(transaction=True)
def test_vale_list_expands_local_stores_and_each_store_has_member_control():
    tenant = Tenant.objects.create(
        nome='Tenant drill-down', slug=f'vale-drill-down-{uuid4().hex}',
    )
    vale = Vale.objects.create(
        tenant=tenant,
        nome='Vale hierárquico',
        sigla=f'VH{uuid4().hex[:4]}',
    )
    loja = Loja.objects.create(tenant=tenant, nome='Loja expansível')
    membro = Membro.objects.create(
        tenant=tenant,
        nome='Membro carregado sob demanda',
    )
    membro.lojas.add(loja)

    outro_tenant = Tenant.objects.create(
        nome='Outro tenant drill-down',
        slug=f'vale-drill-down-outro-{uuid4().hex}',
    )
    Vale.objects.create(
        tenant=outro_tenant,
        nome='Vale de outro tenant',
        sigla=f'VO{uuid4().hex[:4]}',
    )
    Loja.objects.create(tenant=outro_tenant, nome='Loja de outro tenant')

    response = _client_for_tenant(tenant).get('/vales/')
    html = response.content.decode()

    assert response.status_code == 200
    assert 'aria-label="Expandir lojas de Vale hierárquico"' in html
    assert f'data-vale-id="{vale.pk}"' in html
    assert 'Loja expansível' in html
    assert 'aria-label="Expandir membros de Loja expansível"' in html
    assert f'data-loja-id="{loja.pk}"' in html
    assert 'Membro carregado sob demanda' not in html
    assert 'Vale de outro tenant' not in html
    assert 'Loja de outro tenant' not in html
    assert '<details' not in html


@pytest.mark.django_db(transaction=True)
def test_delete_confirmation_lists_complete_contact_details_without_external_guard():
    tenant = Tenant.objects.create(
        nome='Tenant exclusão', slug=f'vale-exclusao-{uuid4().hex}',
    )
    vale = Vale.objects.create(
        tenant=tenant,
        nome='Vale para excluir',
        sigla='VEX',
        secretario_nome='Secretária da exclusão',
        secretario_email='secretaria@gprbr',
        secretario_telefone='(21) 91111-0001',
        tesoureiro_nome='Tesoureiro da exclusão',
        tesoureiro_email='tesouraria@gprbr',
        tesoureiro_telefone='(21) 91111-0002',
    )
    client = _client_for_tenant(tenant, ROLE_ADM)

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
    assert 'Arquivar Vale' in html
    avatar = re.search(
        r'<span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full[^"]*">\s*(.*?)\s*</span>',
        html,
        re.DOTALL,
    )
    assert avatar is not None
    assert avatar.group(1).strip() == 'V'
