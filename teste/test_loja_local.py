"""Tenant-scoped ORM CRUD for local Lojas."""

from uuid import uuid4

import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client

from acesso.models import ROLE_ADM, ROLE_ADMIN_SAAS, ROLE_DELEGADO, Tenant, Usuario
from contatos.models import Loja, Membro, Vale


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def gprb_must_not_be_used(monkeypatch):
    from repositories import gprb_repository

    monkeypatch.setattr(
        gprb_repository,
        'connect',
        lambda: pytest.fail('local Loja views must not connect to GPRB'),
    )


def _tenant_vale(sigla):
    suffix = uuid4().hex
    tenant = Tenant.objects.create(
        nome=sigla,
        slug=f'{sigla.lower()}-{suffix}',
    )
    vale = Vale.objects.create(tenant=tenant, nome=f'Vale {sigla}', sigla=sigla)
    return tenant, vale


def _client_for(tenant, role=ROLE_DELEGADO):
    suffix = uuid4().hex
    user = Usuario.objects.create(
        nome='Editor local',
        email=f'loja-{suffix}@example.test',
        senha=make_password('senha-de-teste'),
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
        'tenant_id': tenant.pk if tenant is not None else None,
    }
    session.save()
    return client


def _loja_data(nome='Loja local'):
    return {
        'nome': nome,
        'numero': '101',
        'telefone': '(41) 90000-0000',
        'email': 'loja@example.test',
        'cidade': 'Curitiba',
        'uf': 'PR',
        'endereco': 'Rua Central, 101, Centro',
        'secretario_nome': 'Secretário da Loja',
        'secretario_telefone': '(41) 91111-0000',
        'tesoureiro_nome': 'Tesoureiro da Loja',
        'tesoureiro_telefone': '(41) 92222-0000',
        'mensalidade': '150,00',
        'situacao': 'ATIVA',
    }


def test_create_loja_uses_selected_tenant_without_posted_vale():
    tenant, vale = _tenant_vale('LCA')
    client = _client_for(tenant, ROLE_ADM)

    response = client.post('/contatos/loja/nova/', _loja_data())

    assert response.status_code == 302
    loja = Loja.objects.get(tenant=tenant, nome='Loja local')
    assert loja.tenant_id == vale.tenant_id
    assert loja.numero == '101'
    assert str(loja.mensalidade) == '150.00'
    assert not response.wsgi_request.POST.get('prefeitura')


def test_loja_form_displays_current_vale_and_has_no_vale_selector():
    tenant, vale = _tenant_vale('LCB')
    client = _client_for(tenant, ROLE_ADM)

    response = client.get('/contatos/loja/nova/')
    html = response.content.decode()

    assert response.status_code == 200
    assert vale.nome in html
    assert 'name="prefeitura"' not in html


def test_loja_list_search_detail_and_edit_are_local():
    tenant, vale = _tenant_vale('LCC')
    loja = Loja.objects.create(tenant=tenant, nome='Estrela do Norte', numero='12')
    client = _client_for(tenant)

    listing = client.get('/contatos/lojas/', {'q': 'Estrela'})
    detail = client.get(f'/contatos/loja/{loja.pk}/')
    edited = client.post(
        f'/contatos/loja/{loja.pk}/editar/',
        _loja_data('Estrela do Sul'),
    )

    assert listing.status_code == 200
    assert 'Estrela do Norte' in listing.content.decode()
    assert detail.status_code == 200
    assert vale.nome in detail.content.decode()
    assert edited.status_code == 302
    assert Loja.objects.filter(pk=loja.pk, tenant=tenant, nome='Estrela do Sul').exists()


def test_other_tenant_cannot_read_or_edit_loja():
    tenant_a, _ = _tenant_vale('LCD')
    tenant_b, _ = _tenant_vale('LCE')
    loja = Loja.objects.create(tenant=tenant_b, nome='Privada')
    client = _client_for(tenant_a)

    detail = client.get(f'/contatos/loja/{loja.pk}/')
    edit = client.post(f'/contatos/loja/{loja.pk}/editar/', _loja_data('Alterada'))

    assert detail.status_code == 404
    assert edit.status_code == 404
    assert Loja.objects.get(pk=loja.pk).nome == 'Privada'


def test_admin_saas_without_selected_tenant_cannot_use_loja_routes():
    client = _client_for(None, ROLE_ADMIN_SAAS)

    response = client.get('/contatos/lojas/')

    assert response.status_code == 403


def test_loja_delete_is_blocked_while_members_are_linked():
    tenant, _ = _tenant_vale('LCF')
    loja = Loja.objects.create(tenant=tenant, nome='Loja ocupada')
    membro = Membro.objects.create(tenant=tenant, nome='Membro vinculado')
    membro.lojas.add(loja)
    client = _client_for(tenant, ROLE_ADM)

    confirmation = client.get(f'/contatos/loja/{loja.pk}/excluir/')
    response = client.post(f'/contatos/loja/{loja.pk}/excluir/')

    assert confirmation.status_code == 200
    assert response.status_code == 200
    assert Loja.objects.filter(pk=loja.pk, tenant=tenant).exists()
    assert response.context['membros'] == 1


def test_loja_members_json_is_local_and_preserves_untrusted_text_as_data():
    tenant, _ = _tenant_vale('LCG')
    other_tenant, _ = _tenant_vale('LCH')
    loja = Loja.objects.create(tenant=tenant, nome='Loja JSON')
    membro = Membro.objects.create(tenant=tenant, nome='<script>alert(1)</script>')
    membro.lojas.add(loja)
    outro = Membro.objects.create(tenant=other_tenant, nome='Outro Vale')
    client = _client_for(tenant)

    response = client.get(f'/contatos/loja/{loja.pk}/membros-json/')

    assert response.status_code == 200
    assert response.json()['membros'] == [
        {'id': membro.pk, 'nome': '<script>alert(1)</script>', 'situacao': 'ATIVO'},
    ]
    assert all(row['id'] != outro.pk for row in response.json()['membros'])
