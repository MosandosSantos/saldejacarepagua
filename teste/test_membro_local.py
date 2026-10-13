"""Tenant-scoped ORM CRUD for local Membros."""

from datetime import date
from uuid import uuid4

import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client

from acesso.models import ROLE_ADMIN_SAAS, ROLE_DELEGADO, Tenant, Usuario
from contatos.models import Loja, Membro, Vale


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def gprb_must_not_be_used(monkeypatch):
    from repositories import gprb_repository

    monkeypatch.setattr(
        gprb_repository,
        'connect',
        lambda: pytest.fail('local Membro views must not connect to GPRB'),
    )


def _tenant_vale(sigla):
    suffix = uuid4().hex
    tenant = Tenant.objects.create(nome=sigla, slug=f'{sigla.lower()}-{suffix}')
    vale = Vale.objects.create(tenant=tenant, nome=f'Vale {sigla}', sigla=sigla)
    return tenant, vale


def _client_for(tenant, role=ROLE_DELEGADO):
    suffix = uuid4().hex
    user = Usuario.objects.create(
        nome='Editor local',
        email=f'membro-{suffix}@example.test',
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


def _membro_data(nome='Membro local', cpf='12345678901'):
    return {
        'nome': nome,
        'cpf': cpf,
        'situacao': 'ATIVO',
        'rito': 'York',
        'cadastro_maconico': 'CAD-101',
        'tipo_admissao': 'REGULAR',
        'data_admissao': '2024-01-10',
        'escolaridade': 'Superior',
        'data_iniciacao': '2020-05-12',
        'potencia': 'Potência local',
        'cargo': 'Membro',
        'condicao': 'REGULAR',
        'data_nascimento': '1980-03-04',
        'nacionalidade': 'Brasileira',
        'naturalidade': 'Curitiba',
        'estado_civil': 'CASADO',
        'pai': 'Pai local',
        'mae': 'Mãe local',
        'identidade': '1234567',
        'orgao_emissor': 'SSP',
        'data_emissao': '2001-02-03',
        'email': 'membro@example.test',
        'celular': '(41) 90000-0000',
        'telefone_urgencia': '(41) 91111-0000',
        'endereco': 'Rua Central',
        'numero': '10',
        'complemento': 'Casa',
        'bairro': 'Centro',
        'cidade': 'Curitiba',
        'uf': 'PR',
        'cep': '80000-000',
        'apresentacao_mx': '2021-03-04',
        'apresentacao_ec': '2022-04-05',
        'armadura_cbcs': '2023-05-06',
        'data_passagem': '2024-06-07',
        'data_elevacao': '2024-07-08',
        'data_instalacao': '2024-08-09',
    }


def test_create_member_locally_and_associate_multiple_same_tenant_lojas():
    tenant, vale = _tenant_vale('MVA')
    primeira = Loja.objects.create(tenant=tenant, nome='Loja Um')
    segunda = Loja.objects.create(tenant=tenant, nome='Loja Dois')
    client = _client_for(tenant)
    data = _membro_data()
    data['lojas'] = [str(primeira.pk), str(segunda.pk)]

    response = client.post('/contatos/membro/novo/', data)

    assert response.status_code == 302
    membro = Membro.objects.get(tenant=tenant, cpf='12345678901')
    assert membro.nome == 'Membro local'
    assert membro.data_admissao == date(2024, 1, 10)
    assert membro.email == 'membro@example.test'
    assert set(membro.lojas.values_list('pk', flat=True)) == {primeira.pk, segunda.pk}
    assert vale.tenant_id == membro.tenant_id


def test_create_member_allows_no_loja_and_does_not_create_login_user():
    tenant, _ = _tenant_vale('MVB')
    client = _client_for(tenant)
    users_before = Usuario.objects.count()

    response = client.post('/contatos/membro/novo/', _membro_data('Sem Loja'))

    assert response.status_code == 302
    membro = Membro.objects.get(tenant=tenant, nome='Sem Loja')
    assert membro.lojas.count() == 0
    assert Usuario.objects.count() == users_before


def test_member_list_search_and_filters_are_scoped_to_tenant():
    tenant_a, vale_a = _tenant_vale('MVC')
    tenant_b, _ = _tenant_vale('MVD')
    loja = Loja.objects.create(tenant=tenant_a, nome='Loja Central')
    visible = Membro.objects.create(
        tenant=tenant_a,
        nome='Ana Visível',
        cpf='11111111111',
        cidade='Curitiba',
        uf='PR',
    )
    visible.lojas.add(loja)
    Membro.objects.create(tenant=tenant_b, nome='Bruno Privado', cpf='22222222222')
    client = _client_for(tenant_a)

    response = client.get('/contatos/', {'q': 'Ana', 'loja': str(loja.pk), 'uf': 'PR'})
    html = response.content.decode()

    assert response.status_code == 200
    assert 'Ana Visível' in html
    assert vale_a.nome in html
    assert 'Bruno Privado' not in html
    assert 'Anuidade:' not in html
    assert 'Presenças' not in html


def test_member_detail_and_edit_round_trip_local_fields_and_lojas():
    tenant, vale = _tenant_vale('MVE')
    loja = Loja.objects.create(tenant=tenant, nome='Loja do Membro')
    membro = Membro.objects.create(tenant=tenant, nome='Membro Antes', cpf='33333333333')
    membro.lojas.add(loja)
    client = _client_for(tenant)

    detail = client.get(f'/contatos/membro/{membro.pk}/')
    data = _membro_data('Membro Depois', '33333333333')
    data['lojas'] = [str(loja.pk)]
    response = client.post(f'/contatos/membro/{membro.pk}/editar/', data)

    assert detail.status_code == 200
    assert vale.nome in detail.content.decode()
    assert response.status_code == 302
    membro.refresh_from_db()
    assert membro.nome == 'Membro Depois'
    assert membro.data_instalacao == date(2024, 8, 9)
    assert list(membro.lojas.values_list('pk', flat=True)) == [loja.pk]


def test_edit_rejects_a_loja_from_another_tenant():
    tenant_a, _ = _tenant_vale('MVF')
    tenant_b, _ = _tenant_vale('MVG')
    membro = Membro.objects.create(tenant=tenant_a, nome='Sem Loja', cpf='44444444444')
    loja_estrangeira = Loja.objects.create(tenant=tenant_b, nome='Loja privada')
    client = _client_for(tenant_a)
    data = _membro_data('Sem Loja', '44444444444')
    data['lojas'] = [str(loja_estrangeira.pk)]

    response = client.post(f'/contatos/membro/{membro.pk}/editar/', data)

    assert response.status_code == 200
    assert response.context['erro']
    membro.refresh_from_db()
    assert membro.lojas.count() == 0
    assert membro.tenant_id == tenant_a.pk


def test_other_tenant_cannot_read_edit_or_delete_member():
    tenant_a, _ = _tenant_vale('MVH')
    tenant_b, _ = _tenant_vale('MVI')
    membro = Membro.objects.create(tenant=tenant_b, nome='Privado', cpf='55555555555')
    client = _client_for(tenant_a)

    detail = client.get(f'/contatos/membro/{membro.pk}/')
    edit = client.post(f'/contatos/membro/{membro.pk}/editar/', _membro_data('Alterado'))
    delete = client.post(f'/contatos/membro/{membro.pk}/excluir/', {'acao': 'excluir'})

    assert detail.status_code == 404
    assert edit.status_code == 404
    assert delete.status_code == 404
    assert Membro.objects.filter(pk=membro.pk, tenant=tenant_b, nome='Privado').exists()


def test_member_can_be_inactivated_and_deleted_locally():
    tenant, _ = _tenant_vale('MVJ')
    membro = Membro.objects.create(tenant=tenant, nome='Inativável', cpf='66666666666')
    client = _client_for(tenant)

    inactivate = client.post(
        f'/contatos/membro/{membro.pk}/excluir/',
        {'acao': 'inativar'},
    )
    membro.refresh_from_db()
    delete = client.post(
        f'/contatos/membro/{membro.pk}/excluir/',
        {'acao': 'excluir'},
    )

    assert inactivate.status_code == 302
    assert membro.situacao == 'INATIVO'
    assert delete.status_code == 302
    assert not Membro.objects.filter(pk=membro.pk, tenant=tenant).exists()
