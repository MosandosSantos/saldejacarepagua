"""Tenant-scoped ORM CRUD for local Membros."""

import unicodedata
from datetime import date
from uuid import uuid4

import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client

from acesso.models import ROLE_DELEGADO, Tenant, Usuario
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
        'graus-TOTAL_FORMS': '1',
        'graus-INITIAL_FORMS': '0',
        'graus-MIN_NUM_FORMS': '0',
        'graus-MAX_NUM_FORMS': '30',
        'graus-0-grau': '',
        'graus-0-data': '',
        'nome': nome,
        'cpf': cpf,
        'situacao': 'ATIVO',
        'rito': 'York',
        'cadastro_maconico': 'CAD-101',
        'tipo_admissao': 'REGULAR',
        'data_admissao': '2024-01-10',
        'escolaridade': 'Superior',
        'potencia': 'CSMB',
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


def test_member_edit_form_uses_fixed_symbolic_power_options():
    tenant, _ = _tenant_vale('MCP')
    membro = Membro.objects.create(tenant=tenant, nome='Membro Potência', potencia='CSMB')
    client = _client_for(tenant)

    response = client.get(f'/contatos/membro/{membro.pk}/editar/')

    assert response.status_code == 200
    assert response.context['sugestoes']['potencias'] == ['COMAB', 'CSMB', 'GOB']
    html = response.content.decode()
    for potencia in ('COMAB', 'CSMB', 'GOB'):
        assert f'value="{potencia}"' in html


def test_member_edit_rejects_symbolic_power_outside_fixed_options():
    tenant, _ = _tenant_vale('MCO')
    membro = Membro.objects.create(tenant=tenant, nome='Membro Potência', potencia='CSMB')
    client = _client_for(tenant)
    data = _membro_data('Membro Editado', cpf='12345678902')
    data['potencia'] = 'Potência inventada'

    response = client.post(f'/contatos/membro/{membro.pk}/editar/', data)

    assert response.status_code == 200
    assert response.context['erro'].startswith('Selecione uma Pot')
    membro.refresh_from_db()
    assert membro.potencia == 'CSMB'


def test_member_list_shows_20_and_filtered_counts_follow_pagination():
    tenant, _ = _tenant_vale('MCR')
    for index in range(27):
        Membro.objects.create(tenant=tenant, nome=f'Filtro {index:02d}')
    for index in range(3):
        Membro.objects.create(tenant=tenant, nome=f'Fora {index:02d}')
    client = _client_for(tenant)

    primeira = client.get('/membros/', {'q': 'Filtro'})
    segunda = client.get('/membros/', {'q': 'Filtro', 'page': '2'})

    assert primeira.status_code == segunda.status_code == 200
    assert primeira.context['page_obj'].paginator.per_page == 20
    assert primeira.context['mostrados'] == 20
    assert primeira.context['total'] == 27
    assert segunda.context['mostrados'] == 7
    assert segunda.context['total'] == 27
    html_ascii = unicodedata.normalize('NFKD', primeira.content.decode('utf-8'))
    html_ascii = html_ascii.encode('ascii', 'ignore').decode('ascii')
    assert '20</b> nesta pagina' in html_ascii


def test_canonical_member_list_shows_20_and_keeps_filter_in_pagination():
    tenant, _ = _tenant_vale('MCS')
    for index in range(27):
        Membro.objects.create(tenant=tenant, nome=f'Filtro canônico {index:02d}')
    for index in range(3):
        Membro.objects.create(tenant=tenant, nome=f'Fora canônico {index:02d}')
    client = _client_for(tenant)

    primeira = client.get('/membros/', {'q': 'Filtro canônico'})
    segunda = client.get('/membros/', {'q': 'Filtro canônico', 'page': '2'})

    assert primeira.status_code == segunda.status_code == 200
    assert primeira.context['page_obj'].paginator.per_page == 20
    assert primeira.context['mostrados'] == 20
    assert primeira.context['total'] == 27
    assert segunda.context['mostrados'] == 7
    assert segunda.context['total'] == 27
    assert '?page=2&q=Filtro+can%C3%B4nico' in primeira.content.decode()


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

    response = client.get('/membros/', {'q': 'Ana', 'loja': str(loja.pk), 'uf': 'PR'})
    html = response.content.decode()

    assert response.status_code == 200
    assert 'Ana Visível' in html
    assert vale_a.nome in html
    assert 'Bruno Privado' not in html
    # Anuidade filter and Presenças column are present in the template (expected)
    # assert 'Presenças' not in html


def test_membro_lista_corpo_filtra_pelas_lojas_vinculadas():
    tenant, _ = _tenant_vale('MCL')
    loja_capitulo = Loja.objects.create(
        tenant=tenant, nome='Loja Capítulo membro', corpo='capitulo',
    )
    loja_perfeicao = Loja.objects.create(
        tenant=tenant, nome='Loja Perfeição membro', corpo='perfeicao',
    )
    capitulo = Membro.objects.create(tenant=tenant, nome='Membro Capítulo')
    perfeicao = Membro.objects.create(tenant=tenant, nome='Membro Perfeição')
    Membro.objects.create(tenant=tenant, nome='Membro sem Loja')
    capitulo.lojas.add(loja_capitulo)
    perfeicao.lojas.add(loja_perfeicao)
    client = _client_for(tenant)

    response = client.get('/membros/', {'corpo': 'capitulo'})
    html = response.content.decode()

    assert response.status_code == 200
    assert 'Membro Capítulo' in html
    assert 'Membro Perfeição' not in html
    assert 'Membro sem Loja' not in html
    assert response.context['total'] == 1


def test_membro_lista_corpo_multiplos_valores_or_sem_duplicar():
    tenant, _ = _tenant_vale('MCM')
    loja_capitulo = Loja.objects.create(
        tenant=tenant, nome='Loja Capítulo múltipla', corpo='capitulo',
    )
    loja_kadosh = Loja.objects.create(
        tenant=tenant, nome='Loja Kadosh múltipla', corpo='kadosh',
    )
    loja_sc33 = Loja.objects.create(
        tenant=tenant, nome='Loja SC33 múltipla', corpo='sc33',
    )
    membro_duas = Membro.objects.create(tenant=tenant, nome='Membro dois corpos')
    membro_sc33 = Membro.objects.create(tenant=tenant, nome='Membro SC33')
    membro_duas.lojas.add(loja_capitulo, loja_kadosh)
    membro_sc33.lojas.add(loja_sc33)
    client = _client_for(tenant)

    response = client.get('/membros/', {
        'corpo': ['capitulo', 'kadosh'],
    })
    html = response.content.decode()

    assert response.status_code == 200
    assert 'Membro dois corpos' in html
    assert 'Membro SC33' not in html
    assert response.context['total'] == 1


def test_membro_lista_corpo_exige_mesma_loja_se_loja_especifica():
    tenant, _ = _tenant_vale('MCN')
    loja_perfeicao = Loja.objects.create(
        tenant=tenant, nome='Loja Perfeição específica', corpo='perfeicao',
    )
    loja_capitulo = Loja.objects.create(
        tenant=tenant, nome='Loja Capítulo específica', corpo='capitulo',
    )
    membro = Membro.objects.create(tenant=tenant, nome='Membro duas lojas')
    membro.lojas.add(loja_perfeicao, loja_capitulo)
    client = _client_for(tenant)

    corresponde = client.get('/membros/', {
        'loja': str(loja_capitulo.pk), 'corpo': 'capitulo',
    })
    contradiz = client.get('/membros/', {
        'loja': str(loja_perfeicao.pk), 'corpo': 'capitulo',
    })

    assert corresponde.status_code == 200
    assert 'Membro duas lojas' in corresponde.content.decode()
    assert contradiz.status_code == 200
    assert 'Membro duas lojas' not in contradiz.content.decode()
    assert contradiz.context['total'] == 0


def test_membro_lista_corpo_ignora_loja_de_outro_tenant():
    tenant, _ = _tenant_vale('MCO')
    tenant_estrangeiro, _ = _tenant_vale('MCP')
    loja_estrangeira = Loja.objects.create(
        tenant=tenant_estrangeiro,
        nome='Loja estrangeira Kadosh',
        corpo='kadosh',
    )
    membro = Membro.objects.create(tenant=tenant, nome='Membro local sem Loja local')
    membro.lojas.add(loja_estrangeira)
    client = _client_for(tenant)

    response = client.get('/membros/', {'corpo': 'kadosh'})

    assert response.status_code == 200
    assert 'Membro local sem Loja local' not in response.content.decode()
    assert response.context['total'] == 0


def test_membro_lista_corpo_combina_com_q_e_outros_filtros():
    tenant, _ = _tenant_vale('MCQ')
    loja_capitulo = Loja.objects.create(
        tenant=tenant, nome='Loja Capítulo busca', corpo='capitulo',
    )
    loja_kadosh = Loja.objects.create(
        tenant=tenant, nome='Loja Kadosh filtrada', corpo='kadosh',
    )
    ana_capitulo = Membro.objects.create(tenant=tenant, nome='Ana Capítulo')
    ana_kadosh = Membro.objects.create(tenant=tenant, nome='Ana Kadosh')
    beto_capitulo = Membro.objects.create(tenant=tenant, nome='Beto Capítulo')
    ana_capitulo.lojas.add(loja_capitulo)
    ana_kadosh.lojas.add(loja_kadosh)
    beto_capitulo.lojas.add(loja_capitulo)
    client = _client_for(tenant)

    response = client.get('/membros/', {
        'q': 'Ana', 'corpo': 'capitulo',
    })
    html = response.content.decode()

    assert response.status_code == 200
    assert 'Ana Capítulo' in html
    assert 'Ana Kadosh' not in html
    assert 'Beto Capítulo' not in html
    assert response.context['total'] == 1


def test_membro_lista_corpo_invalido_nao_amplia_resultados():
    tenant, _ = _tenant_vale('MCR')
    membro = Membro.objects.create(tenant=tenant, nome='Membro corpo inválido')
    loja = Loja.objects.create(tenant=tenant, nome='Loja filtro inválido')
    membro.lojas.add(loja)
    client = _client_for(tenant)

    response = client.get('/membros/', {'corpo': 'invalido'})

    assert response.status_code == 200
    assert 'Membro corpo inválido' not in response.content.decode()
    assert response.context['total'] == 0


def test_membro_lista_corpo_vazio_mantem_filtros_atuais():
    tenant, _ = _tenant_vale('MCS')
    loja = Loja.objects.create(tenant=tenant, nome='Loja sem corpo selecionado')
    com_loja = Membro.objects.create(tenant=tenant, nome='Membro com Loja')
    Membro.objects.create(tenant=tenant, nome='Membro sem Loja')
    com_loja.lojas.add(loja)
    client = _client_for(tenant)

    response = client.get('/membros/')
    html = response.content.decode()

    assert response.status_code == 200
    assert 'Membro com Loja' in html
    assert 'Membro sem Loja' in html
    assert response.context['total'] == 2


def test_membro_lista_preserva_filtros_sem_chips_de_corpo():
    tenant, vale = _tenant_vale('MCT')
    loja = Loja.objects.create(
        tenant=tenant, nome='Loja Capítulo formulário', corpo='capitulo',
    )
    membro = Membro.objects.create(tenant=tenant, nome='Membro filtro formulário')
    membro.lojas.add(loja)
    client = _client_for(tenant)

    response = client.get('/membros/', {
        'q': 'Membro filtro',
        'situacao': 'ATIVO',
        'prefeitura': str(vale.pk),
        'loja': str(loja.pk),
        'corpo': ['capitulo', 'kadosh'],
    })
    html = response.content.decode()
    form_start = html.index('<form method="get"')
    form_end = html.index('</form>', form_start)
    filtros = html[form_start:form_end]

    assert response.status_code == 200
    assert 'name="q" value="Membro filtro"' in filtros
    assert 'name="situacao"' in filtros
    assert 'name="prefeitura"' in filtros
    assert 'name="loja"' in filtros

    # Os chips de Corpos/Graus saíram do card (filtros "perdidos" abaixo)
    assert 'name="corpo"' not in filtros
    assert 'name="grupo_grau"' not in filtros
    assert 'name="corpo" value="capitulo" checked' not in filtros


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


def test_membro_editar_nao_exibe_campos_de_datas_ritualisticas_legadas():
    tenant, _ = _tenant_vale('MVK')
    membro = Membro.objects.create(tenant=tenant, nome='Sem datas antigas')
    client = _client_for(tenant)

    response = client.get(f'/contatos/membro/{membro.pk}/editar/')
    html = response.content.decode()

    assert response.status_code == 200
    assert 'name="data_iniciacao"' not in html
    assert 'name="data_passagem"' not in html
    assert 'name="data_elevacao"' not in html


def test_membro_detalhe_nao_exibe_datas_ritualisticas_legadas():
    tenant, _ = _tenant_vale('MVL')
    membro = Membro.objects.create(tenant=tenant, nome='Sem datas antigas')
    client = _client_for(tenant)

    response = client.get(f'/contatos/membro/{membro.pk}/')
    html = response.content.decode()

    assert response.status_code == 200
    assert 'Data de Iniciação' not in html
    assert 'Data de Passagem' not in html
    assert 'Data de Elevação' not in html
