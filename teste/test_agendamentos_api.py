"""Testes dos endpoints de agendamentos (/api/v1/agendamentos) — auth + isolamento por tenant."""
import pytest
from agendamentos.models import Agendamento
from contatos.models import Contato


@pytest.fixture
def contato_base(tenant_aurora):
    return Contato.objects.create(
        nome='Maria Lima',
        empresa='Clínica Vida',
        seg='nutri',
        tenant=tenant_aurora,
    )


@pytest.mark.django_db(transaction=True)
def test_lista_agendamentos_sem_token_rejeitado(client):
    resp = client.get('/api/v1/agendamentos')

    assert resp.status_code == 401


@pytest.mark.django_db(transaction=True)
def test_lista_agendamentos_vazio(client, headers_operacional):
    resp = client.get('/api/v1/agendamentos', headers=headers_operacional)

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.django_db(transaction=True)
def test_lista_agendamento_com_dados(client, contato_base, headers_operacional):
    Agendamento.objects.create(
        contato=contato_base, hora='10:00', offset_dias=0, tipo='demo', tipo_label='Avaliação'
    )

    resp = client.get('/api/v1/agendamentos', headers=headers_operacional)

    assert resp.status_code == 200
    dados = resp.json()
    assert len(dados) == 1
    item = dados[0]
    assert item['nome'] == 'Maria Lima'
    assert item['empresa'] == 'Clínica Vida'
    assert item['hora'] == '10:00'
    assert item['tipo'] == 'demo'
    assert item['tipoLabel'] == 'Avaliação'
    assert '/' in item['data']
    assert ',' in item['dia']


@pytest.mark.django_db(transaction=True)
def test_agendamentos_ordenados_por_offset_e_hora(client, contato_base, headers_operacional):
    Agendamento.objects.create(
        contato=contato_base, hora='15:00', offset_dias=1, tipo='call', tipo_label='Retorno'
    )
    Agendamento.objects.create(
        contato=contato_base, hora='09:00', offset_dias=0, tipo='reuniao', tipo_label='Consulta'
    )

    resp = client.get('/api/v1/agendamentos', headers=headers_operacional)

    assert resp.status_code == 200
    itens = resp.json()
    assert [item['hora'] for item in itens] == ['09:00', '15:00']


@pytest.mark.django_db(transaction=True)
def test_data_calculada_ignora_fim_de_semana():
    """Offset 0 em um sabado cai em uma segunda-feira (proximo dia util)."""
    from datetime import date

    from api.v1.services.agendamento_service import dia_util

    sabado = date(2026, 8, 8)  # sabado
    proximo_dia_util = dia_util(sabado, 0)

    assert proximo_dia_util.weekday() == 0  # segunda-feira


@pytest.mark.django_db(transaction=True)
def test_excluir_contato_remove_agendamento_da_api(client, contato_base, headers_operacional):
    Agendamento.objects.create(
        contato=contato_base, hora='10:00', offset_dias=0, tipo='demo', tipo_label='Avaliação'
    )

    client.delete(f'/api/v1/contatos/{contato_base.id}', headers=headers_operacional)

    resp = client.get('/api/v1/agendamentos', headers=headers_operacional)
    assert resp.json() == []


@pytest.mark.django_db(transaction=True)
def test_tenant_nao_ve_agendamento_de_outro_tenant(
    client, contato_base, headers_operacional_beta
):
    Agendamento.objects.create(
        contato=contato_base, hora='10:00', offset_dias=0, tipo='demo', tipo_label='Avaliação'
    )

    resp = client.get('/api/v1/agendamentos', headers=headers_operacional_beta)

    assert resp.status_code == 200
    assert resp.json() == []
