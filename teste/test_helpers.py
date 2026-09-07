"""Testes TDD para helpers — funcoes auxiliares do funil.

Ciclo TDD:
  1. Escrever teste falhando (RED)
  2. Verificar falha
  3. Escrever codigo minimo (GREEN)
  4. Refatorar
"""

import pytest
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from contatos.models import Contato, Negocio, criar_negocio


# --- Testes de card_dict ---

@pytest.mark.django_db
def test_card_dict_retorna_campos_obrigatorios(tenant_aurora):
    """RED: card_dict deve retornar todos os campos necessarios para o kanban."""
    from recepcao.views.helpers import card_dict

    contato = Contato.objects.create(
        nome='Maria Card',
        tel='(11) 99999-0000',
        email='maria@card.com',
        seg='odonto',
        tenant=tenant_aurora,
    )
    negocio = criar_negocio(contato, stage='suplica', valor=Decimal('1500'), tenant_id=tenant_aurora.id)
    stage_map = {'suplica': {'key': 'suplica', 'name': 'Suplica', 'color': '#94a3b8'}}

    card = card_dict(negocio, stage_map)

    assert card['id'] == negocio.id
    assert card['contato_id'] == contato.id
    assert card['nome'] == 'Maria Card'
    assert card['valor'] is not None
    assert 'score' in card


# --- Testes de cards_do_kanban ---

@pytest.mark.django_db
def test_cards_do_kanban_agrupa_por_stage(tenant_aurora):
    """RED: cards_do_kanban deve agrupar negocios por etapa."""
    from recepcao.views.helpers import cards_do_kanban

    c1 = Contato.objects.create(nome='Lead 1', tenant=tenant_aurora)
    c2 = Contato.objects.create(nome='Lead 2', tenant=tenant_aurora)
    criar_negocio(c1, stage='suplica', tenant_id=tenant_aurora.id)
    criar_negocio(c2, stage='prefeito', tenant_id=tenant_aurora.id)

    stages = [
        {'key': 'suplica', 'name': 'Suplica', 'color': '#94a3b8'},
        {'key': 'prefeito', 'name': 'Prefeito', 'color': '#38bdf8'},
    ]

    colunas, por_stage = cards_do_kanban(Negocio.objects.filter(tenant_id=tenant_aurora.id), stages)

    assert len(colunas) == 2
    assert colunas[0]['key'] == 'suplica'
    assert colunas[0]['count'] == 1
    assert colunas[1]['key'] == 'prefeito'
    assert colunas[1]['count'] == 1


@pytest.mark.django_db
def test_cards_do_kanban_limita_30_cards(tenant_aurora):
    """RED: cards_do_kanban deve limitar a 30 cards por coluna."""
    from recepcao.views.helpers import cards_do_kanban

    for i in range(35):
        c = Contato.objects.create(nome=f'Lead {i}', tenant=tenant_aurora)
        criar_negocio(c, stage='suplica', tenant_id=tenant_aurora.id)

    stages = [{'key': 'suplica', 'name': 'Suplica', 'color': '#94a3b8'}]
    colunas, _ = cards_do_kanban(Negocio.objects.filter(tenant_id=tenant_aurora.id), stages)

    assert colunas[0]['count'] == 35
    assert len(colunas[0]['cards']) == 30
    assert colunas[0]['ocultos'] == 5


# --- Testes de estagnados_da_lista ---

@pytest.mark.django_db
def test_estagnados_da_lista_filtra_por_dias(tenant_aurora):
    """RED: estagnados_da_lista deve retornar negocios parados ha X dias."""
    from recepcao.views.helpers import estagnados_da_lista

    c1 = Contato.objects.create(nome='Ativo', tenant=tenant_aurora)
    c2 = Contato.objects.create(nome='Estagnado', tenant=tenant_aurora)

    n1 = criar_negocio(c1, stage='suplica', tenant_id=tenant_aurora.id)
    n2 = criar_negocio(c2, stage='suplica', tenant_id=tenant_aurora.id)

    # Simula negocio estagnado (atualizado ha 10 dias)
    # Usa update() em vez de save() porque auto_now=True sobrescreve o valor
    Negocio.objects.filter(pk=n2.pk).update(updated_at=timezone.now() - timedelta(days=10))

    # Recarrega do banco para ter o valor correto
    n1.refresh_from_db()
    n2.refresh_from_db()

    negocios = [n1, n2]
    estagnados = estagnados_da_lista(negocios, dias=7)

    assert len(estagnados) == 1
    assert estagnados[0]['nome'] == 'Estagnado'


@pytest.mark.django_db
def test_estagnados_da_lista_limite_12(tenant_aurora):
    """RED: estagnados_da_lista deve retornar no maximo 12."""
    from recepcao.views.helpers import estagnados_da_lista

    negocios = []
    for i in range(20):
        c = Contato.objects.create(nome=f'Lead {i}', tenant=tenant_aurora)
        n = criar_negocio(c, stage='suplica', tenant_id=tenant_aurora.id)
        n.updated_at = timezone.now() - timedelta(days=10)
        n.save(update_fields=['updated_at'])
        negocios.append(n)

    estagnados = estagnados_da_lista(negocios, dias=7)

    assert len(estagnados) <= 12


# --- Testes de prefeitura_info ---

def test_prefeitura_info_retorna_vazio_se_sem_valor():
    """RED: prefeitura_info deve retornar dict vazio se valor for None."""
    from recepcao.views.helpers import prefeitura_info

    result = prefeitura_info(None)

    assert result == {'nome': '', 'sigla': ''}


def test_prefeitura_info_retorna_vazio_se_string_vazia():
    """RED: prefeitura_info deve retornar dict vazio se valor for string vazia."""
    from recepcao.views.helpers import prefeitura_info

    result = prefeitura_info('')

    assert result == {'nome': '', 'sigla': ''}


# --- Testes de parse_lead_data ---

def test_parse_lead_data_extrai_nome():
    """RED: parse_lead_data deve extrair nome corretamente."""
    from recepcao.views.lead_service import parse_lead_data

    dados = parse_lead_data({'nome': '  Maria  '})

    assert dados.nome == 'Maria'


def test_parse_lead_data_extrai_email_lower():
    """RED: parse_lead_data deve normalizar email para lowercase."""
    from recepcao.views.lead_service import parse_lead_data

    dados = parse_lead_data({'email': ' MARIA@TEST.COM '})

    assert dados.email == 'maria@test.com'


def test_parse_lead_data_extrai_valor_brl():
    """RED: parse_lead_data deve converter valor BRL para Decimal."""
    from recepcao.views.lead_service import parse_lead_data

    dados = parse_lead_data({'valor': '1.500,00'})

    assert dados.valor == Decimal('1500.00')
