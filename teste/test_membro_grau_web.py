"""Web tests for editing a member's dated degree history."""
from datetime import date, timedelta
from uuid import uuid4

import pytest
from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client
from django.utils import timezone

from acesso.models import ROLE_ADM, Tenant, Usuario
from contatos.models import Grau, GrauMembro, Membro, Vale

pytestmark = pytest.mark.django_db(transaction=True)

SENHA = 'senha123'


@pytest.fixture
def _mundo_membro():
    """Tenant + Vale + ADM + membro criado para os testes web de grau."""
    suffix = uuid4().hex
    tenant = Tenant.objects.create(
        nome='Teste Grau', slug=f'teste-grau-{suffix}',
    )
    vale = Vale.objects.create(
        tenant=tenant, nome=f'Vale {suffix}', sigla=f'VG{suffix[:2]}',
    )
    adm = Usuario.objects.create(
        nome='ADM Grau',
        email=f'membro-grau-{suffix}@example.test',
        senha=make_password(SENHA),
        role=ROLE_ADM,
        tenant=tenant,
    )
    membro = Membro.objects.create(
        tenant=tenant, nome='Membro De Grau', situacao='ATIVO',
    )
    return {'tenant': tenant, 'vale': vale, 'adm': adm, 'membro': membro}


def _client(adm):
    client = Client()
    resp = client.post('/login/', {'email': adm.email, 'senha': SENHA})
    assert resp.status_code == 302
    return client


def _formset_data(membro, rows, initial_forms=0):
    data = {
        'nome': membro.nome,
        'graus-TOTAL_FORMS': str(len(rows)),
        'graus-INITIAL_FORMS': str(initial_forms),
        'graus-MIN_NUM_FORMS': '0',
        'graus-MAX_NUM_FORMS': '1000',
    }
    for index, row in enumerate(rows):
        for field in ('id', 'grau', 'data', 'DELETE'):
            if field in row:
                data[f'graus-{index}-{field}'] = str(row[field])
    return data


def test_seed_graus_cria_catalogo_4_a_33_idempotente():
    call_command('seed_graus', verbosity=0)
    assert Grau.objects.count() == 30  # 4..33
    assert not {g.numero for g in Grau.objects.all()} - set(range(4, 34))

    # Idempotente
    call_command('seed_graus', verbosity=0)
    assert Grau.objects.count() == 30


def test_editar_membro_grava_grau_no_historico(_mundo_membro):
    call_command('seed_graus', verbosity=0)
    mundo = _mundo_membro
    client = _client(mundo['adm'])
    grau_14 = Grau.objects.get(numero=14)

    response = client.post(
        f'/membros/{mundo["membro"].pk}/editar/',
        _formset_data(mundo['membro'], [
            {'grau': grau_14.pk, 'data': '2020-01-02'},
        ]),
    )

    assert response.status_code == 302
    historico = GrauMembro.objects.filter(
        membro=mundo['membro'], grau=grau_14,
    )
    assert historico.count() == 1
    registro = mundo['membro'].graus.get(grau=grau_14)
    assert registro.grau_id == grau_14.pk
    assert registro.data == date(2020, 1, 2)


def test_editar_membro_grau_e_idempotente(_mundo_membro):
    call_command('seed_graus', verbosity=0)
    mundo = _mundo_membro
    client = _client(mundo['adm'])
    grau_7 = Grau.objects.get(numero=7)

    response = client.post(
        f'/membros/{mundo["membro"].pk}/editar/',
        _formset_data(mundo['membro'], [
            {'grau': grau_7.pk, 'data': '2018-04-05'},
        ]),
    )
    assert response.status_code == 302
    registro = GrauMembro.objects.get(membro=mundo['membro'], grau=grau_7)
    response = client.post(
        f'/membros/{mundo["membro"].pk}/editar/',
        _formset_data(mundo['membro'], [
            {'id': registro.pk, 'grau': grau_7.pk, 'data': '2018-04-05'},
        ], initial_forms=1),
    )

    assert response.status_code == 302
    assert GrauMembro.objects.filter(membro=mundo['membro']).count() == 1


def test_editar_membro_sem_grau_nao_altera_historico(_mundo_membro):
    call_command('seed_graus', verbosity=0)
    mundo = _mundo_membro
    client = _client(mundo['adm'])

    response = client.post(
        f'/membros/{mundo["membro"].pk}/editar/',
        _formset_data(mundo['membro'], [{}]),
    )

    assert response.status_code == 302
    assert GrauMembro.objects.filter(membro=mundo['membro']).count() == 0


def test_form_editar_exibe_formset_de_graus(_mundo_membro):
    call_command('seed_graus', verbosity=0)
    mundo = _mundo_membro
    client = _client(mundo['adm'])

    response = client.get(f'/membros/{mundo["membro"].pk}/editar/')
    html = response.content.decode()

    assert response.status_code == 200
    assert 'name="graus-TOTAL_FORMS"' in html
    assert 'name="graus-0-grau"' in html
    assert 'Grau 4' in html


def test_editar_membro_grava_varios_graus_com_datas_independentes(_mundo_membro):
    call_command('seed_graus', verbosity=0)
    mundo = _mundo_membro
    client = _client(mundo['adm'])
    graus = {g.numero: g for g in Grau.objects.filter(numero__in=(10, 11, 18))}
    dados = _formset_data(mundo['membro'], [
        {'grau': graus[10].pk, 'data': '2010-02-03'},
        {'grau': graus[11].pk, 'data': '2014-05-06'},
        {'grau': graus[18].pk, 'data': '2020-08-09'},
    ])

    response = client.post(f'/membros/{mundo["membro"].pk}/editar/', dados)

    assert response.status_code == 302
    assert list(
        mundo['membro'].graus.order_by('grau__numero').values_list(
            'grau__numero', 'data',
        ),
    ) == [
        (10, date(2010, 2, 3)),
        (11, date(2014, 5, 6)),
        (18, date(2020, 8, 9)),
    ]


def test_editar_membro_atualiza_data_e_remove_grau(_mundo_membro):
    call_command('seed_graus', verbosity=0)
    mundo = _mundo_membro
    membro = mundo['membro']
    grau_10 = Grau.objects.get(numero=10)
    grau_11 = Grau.objects.get(numero=11)
    manter = GrauMembro.objects.create(
        tenant=mundo['tenant'], membro=membro, grau=grau_10, data='2010-01-01',
    )
    remover = GrauMembro.objects.create(
        tenant=mundo['tenant'], membro=membro, grau=grau_11, data='2012-01-01',
    )
    client = _client(mundo['adm'])
    dados = _formset_data(membro, [
        {'id': manter.pk, 'grau': grau_10.pk, 'data': '2011-02-03'},
        {
            'id': remover.pk, 'grau': grau_11.pk,
            'data': '2012-01-01', 'DELETE': 'on',
        },
    ], initial_forms=2)

    response = client.post(f'/membros/{membro.pk}/editar/', dados)

    assert response.status_code == 302
    manter.refresh_from_db()
    assert manter.data == date(2011, 2, 3)
    assert not GrauMembro.objects.filter(pk=remover.pk).exists()


def test_formset_rejeita_grau_duplicado_sem_salvar_parcialmente(_mundo_membro):
    call_command('seed_graus', verbosity=0)
    mundo = _mundo_membro
    client = _client(mundo['adm'])
    grau = Grau.objects.get(numero=10)
    dados = _formset_data(mundo['membro'], [
        {'grau': grau.pk, 'data': '2010-02-03'},
        {'grau': grau.pk, 'data': '2011-02-03'},
    ])

    response = client.post(f'/membros/{mundo["membro"].pk}/editar/', dados)

    assert response.status_code == 200
    assert GrauMembro.objects.filter(membro=mundo['membro']).count() == 0


def test_db_conflict_for_duplicate_grade_reports_grade_and_rolls_back_member(_mundo_membro):
    call_command('seed_graus', verbosity=0)
    mundo = _mundo_membro
    membro = mundo['membro']
    grau = Grau.objects.get(numero=10)
    existente = GrauMembro.objects.create(
        tenant=mundo['tenant'], membro=membro, grau=grau, data='2010-01-01',
    )
    client = _client(mundo['adm'])
    dados = _formset_data(membro, [
        {'grau': grau.pk, 'data': '2011-01-01'},
    ], initial_forms=0)
    dados['nome'] = 'Nome que não pode ser salvo parcialmente'

    response = client.post(f'/membros/{membro.pk}/editar/', dados)

    assert response.status_code == 200
    assert 'grau' in response.context['erro'].casefold()
    membro.refresh_from_db()
    existente.refresh_from_db()
    assert membro.nome == 'Membro De Grau'
    assert existente.data == date(2010, 1, 1)
    assert GrauMembro.objects.filter(membro=membro).count() == 1


def test_formset_rejeita_data_vazia_sem_salvar_parcialmente(_mundo_membro):
    call_command('seed_graus', verbosity=0)
    mundo = _mundo_membro
    client = _client(mundo['adm'])
    grau = Grau.objects.get(numero=10)
    dados = _formset_data(mundo['membro'], [
        {'grau': grau.pk, 'data': ''},
    ])

    response = client.post(f'/membros/{mundo["membro"].pk}/editar/', dados)

    assert response.status_code == 200
    assert GrauMembro.objects.filter(membro=mundo['membro']).count() == 0


def test_formset_rejeita_data_futura_sem_salvar_parcialmente(_mundo_membro):
    call_command('seed_graus', verbosity=0)
    mundo = _mundo_membro
    client = _client(mundo['adm'])
    grau = Grau.objects.get(numero=10)
    data_futura = (timezone.localdate() + timedelta(days=1)).isoformat()
    dados = _formset_data(mundo['membro'], [
        {'grau': grau.pk, 'data': data_futura},
    ])

    response = client.post(f'/membros/{mundo["membro"].pk}/editar/', dados)

    assert response.status_code == 200
    assert GrauMembro.objects.filter(membro=mundo['membro']).count() == 0


def test_formset_nao_altera_historico_de_outro_membro(_mundo_membro):
    call_command('seed_graus', verbosity=0)
    mundo = _mundo_membro
    outro = Membro.objects.create(tenant=mundo['tenant'], nome='Outro Membro')
    grau = Grau.objects.get(numero=10)
    historico_alheio = GrauMembro.objects.create(
        tenant=mundo['tenant'], membro=outro, grau=grau, data='2010-01-01',
    )
    client = _client(mundo['adm'])
    dados = _formset_data(mundo['membro'], [
        {'id': historico_alheio.pk, 'grau': grau.pk, 'data': '2011-01-01'},
    ], initial_forms=1)

    response = client.post(f'/membros/{mundo["membro"].pk}/editar/', dados)

    assert response.status_code == 200
    historico_alheio.refresh_from_db()
    assert historico_alheio.data == date(2010, 1, 1)
    assert not GrauMembro.objects.filter(membro=mundo['membro']).exists()


@pytest.mark.parametrize('numero', (3, 34))
def test_catalogo_rejeita_graus_fora_da_faixa(numero):
    with pytest.raises(IntegrityError), transaction.atomic():
        Grau.objects.create(numero=numero, nome=f'Grau {numero}')


def test_atribuir_graus_iniciais_popula_faixa_4_a_13_e_e_idempotente():
    """Membros sem grau recebem um grau em 4..13; quem já tem não é tocado."""
    call_command('seed_graus', verbosity=0)
    tenant = Tenant.objects.create(
        nome='Teste Distribuicao', slug=f'teste-dist-{uuid4().hex}',
    )
    com_grau = Membro.objects.create(
        tenant=tenant, nome='Já Tem Grau', situacao='ATIVO',
    )
    GrauMembro.objects.create(
        tenant=tenant, membro=com_grau, grau=Grau.objects.get(numero=12),
        data='2026-01-01',
    )
    elegiveis = [
        Membro.objects.create(
            tenant=tenant, nome=f'Sem Grau {i}', situacao='ATIVO',
        )
        for i in range(15)
    ]
    inativo = Membro.objects.create(
        tenant=tenant, nome='Inativo', situacao='INATIVO',
    )

    call_command('atribuir_graus_iniciais', verbosity=0)

    for membro in elegiveis:
        registrado = GrauMembro.objects.filter(membro=membro)
        assert registrado.count() == 1, membro.nome
        numero = registrado.first().grau.numero
        assert 4 <= numero <= 13
    # Idempotente: segunda execução não duplica nem troca os graus
    antes = {gm.membro_id: gm.grau_id for gm in GrauMembro.objects.all()}
    call_command('atribuir_graus_iniciais', verbosity=0)
    depois = {gm.membro_id: gm.grau_id for gm in GrauMembro.objects.all()}
    assert antes == depois
    # Quem já tinha grau e o inativo ficam fora da atribuição
    assert GrauMembro.objects.filter(membro=com_grau).count() == 1
    assert GrauMembro.objects.filter(membro=inativo).count() == 0
