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
        'corpo': 'perfeicao',
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


def test_new_loja_form_keeps_president_contact_but_not_member_selector():
    tenant, _ = _tenant_vale('LCP')
    response = _client_for(tenant, ROLE_ADM).get('/contatos/loja/nova/')
    html = response.content.decode()

    assert response.status_code == 200
    assert 'name="deputado_mestre"' not in html
    assert 'name="presidente_nome"' in html
    assert 'name="email"' in html
    assert 'name="telefone"' in html


def test_new_loja_form_uses_text_inputs_for_secretario_and_tesoureiro_names():
    tenant, _ = _tenant_vale('LCN')
    response = _client_for(tenant, ROLE_ADM).get('/contatos/loja/nova/')
    html = response.content.decode()

    assert response.status_code == 200
    assert 'type="text" id="secretario_nome" name="secretario_nome"' in html
    assert 'type="text" id="tesoureiro_nome" name="tesoureiro_nome"' in html
    assert 'name="secretario"' not in html
    assert 'name="tesoureiro"' not in html


def test_new_loja_ignores_a_stale_president_member_post():
    tenant, vale = _tenant_vale('LCR')
    presidente = Membro.objects.create(
        tenant=tenant,
        nome='Presidente fora do corpo',
    )
    response = _client_for(tenant, ROLE_ADM).post(
        '/contatos/loja/nova/',
        {
            **_loja_data('Loja sem vínculo de presidente'),
            'vale_id': str(vale.pk),
            'presidente_nome': 'Presidente de contato',
            'deputado_mestre': str(presidente.pk),
        },
    )

    assert response.status_code == 302
    loja = Loja.objects.get(
        tenant=tenant,
        nome='Loja sem vínculo de presidente',
    )
    assert loja.deputado_mestre_id is None
    assert loja.presidente_nome == 'Presidente de contato'
    assert not loja.membros.filter(pk=presidente.pk).exists()


def test_new_loja_saves_official_names_without_linking_them_as_members():
    tenant, vale = _tenant_vale('LCO')
    secretario = Membro.objects.create(tenant=tenant, nome='Membro Secretário')
    tesoureiro = Membro.objects.create(tenant=tenant, nome='Membro Tesoureiro')
    response = _client_for(tenant, ROLE_ADM).post(
        '/contatos/loja/nova/',
        {
            **_loja_data('Loja com cargos em texto'),
            'vale_id': str(vale.pk),
            'secretario_nome': 'Secretário em texto',
            'tesoureiro_nome': 'Tesoureiro em texto',
            'secretario': str(secretario.pk),
            'tesoureiro': str(tesoureiro.pk),
        },
    )

    assert response.status_code == 302
    loja = Loja.objects.get(tenant=tenant, nome='Loja com cargos em texto')
    assert loja.secretario_id is None
    assert loja.tesoureiro_id is None
    assert loja.secretario_nome == 'Secretário em texto'
    assert loja.tesoureiro_nome == 'Tesoureiro em texto'
    assert not loja.membros.filter(pk__in=[secretario.pk, tesoureiro.pk]).exists()


def test_loja_form_displays_current_vale_and_has_no_vale_selector():
    tenant, vale = _tenant_vale('LCB')
    client = _client_for(tenant, ROLE_ADM)

    response = client.get('/contatos/loja/nova/')
    html = response.content.decode()

    assert response.status_code == 200
    assert vale.nome in html
    assert 'name="prefeitura"' not in html


def test_create_loja_saves_selected_corpo():
    tenant, vale = _tenant_vale('LCX')
    client = _client_for(tenant, ROLE_ADM)
    payload = {**_loja_data(), 'vale_id': str(vale.pk), 'corpo': 'capitulo'}

    response = client.post('/contatos/loja/nova/', payload)

    assert response.status_code == 302
    assert Loja.objects.get(tenant=tenant, nome='Loja local').corpo == 'capitulo'


@pytest.mark.parametrize('corpo', [None, 'nao-existe'])
def test_create_loja_rejects_missing_or_invalid_corpo(corpo):
    tenant, vale = _tenant_vale('LCY')
    client = _client_for(tenant, ROLE_ADM)
    payload = {**_loja_data(), 'vale_id': str(vale.pk)}
    if corpo is None:
        payload.pop('corpo')
    else:
        payload['corpo'] = corpo
    total_antes = Loja.objects.count()

    response = client.post('/contatos/loja/nova/', payload)

    assert response.status_code == 200
    assert response.context['erro']
    assert Loja.objects.count() == total_antes


def test_edit_loja_saves_selected_corpo():
    tenant, _ = _tenant_vale('LCZ')
    loja = Loja.objects.create(tenant=tenant, nome='Loja para alterar corpo')
    client = _client_for(tenant, ROLE_ADM)
    payload = _loja_data('Loja para alterar corpo')
    payload['corpo'] = 'capitulo'

    response = client.post(f'/contatos/loja/{loja.pk}/editar/', payload)

    assert response.status_code == 302
    loja.refresh_from_db()
    assert loja.corpo == 'capitulo'


@pytest.mark.parametrize('corpo', [None, 'nao-existe'])
def test_edit_loja_rejects_missing_or_invalid_corpo_without_changing_it(corpo):
    tenant, _ = _tenant_vale('LDA')
    loja = Loja.objects.create(tenant=tenant, nome='Loja corpo protegido')
    client = _client_for(tenant, ROLE_ADM)
    payload = _loja_data('Nome não deve ser salvo')
    if corpo is None:
        payload.pop('corpo')
    else:
        payload['corpo'] = corpo

    response = client.post(f'/contatos/loja/{loja.pk}/editar/', payload)

    assert response.status_code == 200
    assert response.context['erro']
    assert response.context['corpo_atual'] == 'perfeicao'
    loja.refresh_from_db()
    assert loja.nome == 'Loja corpo protegido'
    assert loja.corpo == 'perfeicao'


def test_loja_create_and_edit_forms_render_corpo_choices():
    tenant, _ = _tenant_vale('LDB')
    loja = Loja.objects.create(
        tenant=tenant, nome='Loja corpo Capítulo', corpo='capitulo',
    )
    client = _client_for(tenant, ROLE_ADM)

    create = client.get('/contatos/loja/nova/')
    edit = client.get(f'/contatos/loja/{loja.pk}/editar/')
    create_html = create.content.decode()
    edit_html = edit.content.decode()

    assert create.status_code == 200
    assert edit.status_code == 200
    assert '<select id="corpo" name="corpo" required' in create_html
    assert 'value="" selected' in create_html
    assert 'Selecione o Corpo' in create_html
    for value, label in Loja.CORPO_CHOICES:
        assert f'<option value="{value}"' in create_html
        assert label in create_html
    assert 'value="capitulo" selected' in edit_html
    assert 'Capítulo' in edit_html


def test_loja_list_and_detail_display_corpo():
    tenant, _ = _tenant_vale('LDC')
    loja = Loja.objects.create(
        tenant=tenant, nome='Loja com Corpo visível', corpo='capitulo',
    )
    client = _client_for(tenant)

    listing = client.get('/contatos/lojas/')
    detail = client.get(f'/contatos/loja/{loja.pk}/')

    assert listing.status_code == 200
    assert detail.status_code == 200
    assert 'Capítulo' in listing.content.decode()
    assert 'Capítulo' in detail.content.decode()


def test_loja_lista_corpo_filtra_pelo_selecionado():
    tenant, _ = _tenant_vale('LDE')
    Loja.objects.create(tenant=tenant, nome='Loja Capítulo filtro', corpo='capitulo')
    Loja.objects.create(tenant=tenant, nome='Loja Kadosh filtro', corpo='kadosh')
    client = _client_for(tenant)

    response = client.get('/contatos/lojas/', {'corpo': 'capitulo'})
    html = response.content.decode()

    assert response.status_code == 200
    assert 'Loja Capítulo filtro' in html
    assert 'Loja Kadosh filtro' not in html
    assert response.context['total'] == 1


def test_loja_lista_corpo_multiplos_valores_combinam_por_or_sem_duplicar():
    tenant, _ = _tenant_vale('LDF')
    Loja.objects.create(tenant=tenant, nome='Loja Capítulo OR', corpo='capitulo')
    Loja.objects.create(tenant=tenant, nome='Loja Kadosh OR', corpo='kadosh')
    Loja.objects.create(tenant=tenant, nome='Loja SC33 OR', corpo='sc33')
    client = _client_for(tenant)

    response = client.get('/contatos/lojas/', {
        'corpo': ['capitulo', 'kadosh'],
    })
    html = response.content.decode()

    assert response.status_code == 200
    assert 'Loja Capítulo OR' in html
    assert 'Loja Kadosh OR' in html
    assert 'Loja SC33 OR' not in html
    assert response.context['total'] == 2


def test_loja_lista_corpo_combina_com_busca_por_and():
    tenant, _ = _tenant_vale('LDG')
    Loja.objects.create(
        tenant=tenant, nome='Estrela Capítulo', corpo='capitulo',
    )
    Loja.objects.create(
        tenant=tenant, nome='Aurora Capítulo', corpo='capitulo',
    )
    Loja.objects.create(tenant=tenant, nome='Estrela Kadosh', corpo='kadosh')
    client = _client_for(tenant)

    response = client.get('/contatos/lojas/', {
        'q': 'Estrela', 'corpo': 'capitulo',
    })
    html = response.content.decode()

    assert response.status_code == 200
    assert 'Estrela Capítulo' in html
    assert 'Aurora Capítulo' not in html
    assert 'Estrela Kadosh' not in html
    assert response.context['total'] == 1


def test_loja_lista_corpo_desconhecido_nao_amplia_resultados():
    tenant, _ = _tenant_vale('LDH')
    Loja.objects.create(tenant=tenant, nome='Loja que não deve aparecer')
    client = _client_for(tenant)

    response = client.get('/contatos/lojas/', {'corpo': 'nao-existe'})

    assert response.status_code == 200
    assert 'Loja que não deve aparecer' not in response.content.decode()
    assert response.context['total'] == 0


def test_loja_lista_corpo_vazio_mantem_todas_as_lojas():
    tenant, _ = _tenant_vale('LDI')
    Loja.objects.create(tenant=tenant, nome='Loja sem filtro Perfeição', corpo='perfeicao')
    Loja.objects.create(tenant=tenant, nome='Loja sem filtro Capítulo', corpo='capitulo')
    client = _client_for(tenant)

    response = client.get('/contatos/lojas/')
    html = response.content.decode()

    assert response.status_code == 200
    assert 'Loja sem filtro Perfeição' in html
    assert 'Loja sem filtro Capítulo' in html
    assert response.context['total'] == 2


def test_loja_lista_exibe_corpos_e_preserva_selecao():
    tenant, _ = _tenant_vale('LDJ')
    client = _client_for(tenant)

    response = client.get('/contatos/lojas/', {
        'q': 'Estrela', 'corpo': ['capitulo', 'kadosh'],
    })
    html = response.content.decode()
    form_start = html.index('<form method="get" action="/lojas/"')
    form_end = html.index('</form>', form_start)
    filtros = html[form_start:form_end]

    assert response.status_code == 200
    assert 'name="q" value="Estrela"' in filtros
    assert 'name="corpo" value="capitulo" checked' in filtros
    assert 'name="corpo" value="kadosh" checked' in filtros
    assert 'name="corpo" value="perfeicao"' in filtros
    assert 'name="corpo" value="todos"' not in filtros


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


def test_admin_saas_without_selected_tenant_reads_lojas_but_cannot_create():
    """Leitura é global (drill-down de /vales/); criação exige Vale explícito."""
    tenant, _ = _tenant_vale('LDA')
    Loja.objects.create(tenant=tenant, nome='Loja visível global')
    client = _client_for(None, ROLE_ADMIN_SAAS)

    listing = client.get('/contatos/lojas/')
    assert listing.status_code == 200
    assert 'Loja visível global' in listing.content.decode()

    total_antes = Loja.objects.count()
    response = client.post('/contatos/loja/nova/', {'nome': 'Loja sem Vale', 'numero': '1'})

    assert response.status_code == 200
    assert 'Vale' in response.content.decode()
    assert Loja.objects.count() == total_antes


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
        {
            'id': membro.pk,
            'nome': '<script>alert(1)</script>',
            'situacao': 'ATIVO',
            'cadastro': '',
            'grau': None,
            'presenca': None,
            'presenca_abaixo_50': False,
        },
    ]
    assert all(row['id'] != outro.pk for row in response.json()['membros'])
