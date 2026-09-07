"""Testes TDD para LeadService — cadastro de leads no funil.

Ciclo TDD:
  1. Escrever teste falhando (RED)
  2. Verificar falha
  3. Escrever codigo minimo (GREEN)
  4. Refatorar
"""

import pytest
from decimal import Decimal

from contatos.models import Contato, Negocio


# --- Testes de validacao ---

@pytest.mark.django_db
def test_lead_service_rejeita_nome_vazio(tenant_aurora):
    """RED: LeadService deve rejeitar lead sem nome."""
    from recepcao.views.lead_service import LeadService, LeadData, LeadValidationError

    service = LeadService()
    dados = LeadData(nome='', stage='suplica')

    with pytest.raises(LeadValidationError) as exc_info:
        service.criar_lead(dados, tenant_id=tenant_aurora.id)

    assert 'nome' in str(exc_info.value.erros).lower()


@pytest.mark.django_db
def test_lead_service_rejeita_stage_invalido(tenant_aurora):
    """RED: LeadService deve rejeitar etapa que nao existe no pipeline."""
    from recepcao.views.lead_service import LeadService, LeadData, LeadValidationError

    service = LeadService()
    dados = LeadData(nome='Teste', stage='etapa_inexistente')

    with pytest.raises(LeadValidationError) as exc_info:
        service.criar_lead(dados, tenant_id=tenant_aurora.id)

    assert 'etapa' in str(exc_info.value.erros).lower()


@pytest.mark.django_db
def test_lead_service_rejeita_valor_negativo(tenant_aurora):
    """RED: LeadService deve rejeitar valor negativo."""
    from recepcao.views.lead_service import LeadService, LeadData, LeadValidationError

    service = LeadService()
    dados = LeadData(nome='Teste', stage='suplica', valor=Decimal('-100'))

    with pytest.raises(LeadValidationError) as exc_info:
        service.criar_lead(dados, tenant_id=tenant_aurora.id)

    assert 'negativo' in str(exc_info.value.erros).lower()


@pytest.mark.django_db
def test_lead_service_rejeita_origem_invalida(tenant_aurora):
    """RED: LeadService deve rejeitar origem nao listada."""
    from recepcao.views.lead_service import LeadService, LeadData, LeadValidationError

    service = LeadService()
    dados = LeadData(nome='Teste', stage='suplica', origem='OrigemFantasia')

    with pytest.raises(LeadValidationError) as exc_info:
        service.criar_lead(dados, tenant_id=tenant_aurora.id)

    assert 'origem' in str(exc_info.value.erros).lower()


# --- Testes de criacao ---

@pytest.mark.django_db
def test_lead_service_cria_contato_e_negocio(tenant_aurora):
    """GREEN: LeadService deve criar contato + negocio corretamente."""
    from recepcao.views.lead_service import LeadService, LeadData

    service = LeadService()
    dados = LeadData(
        nome='Maria TDD',
        tel='(11) 99999-0000',
        email='maria@tdd.com',
        stage='suplica',
        valor=Decimal('1500.00'),
    )

    result = service.criar_lead(dados, tenant_id=tenant_aurora.id)

    assert result.contato is not None
    assert result.negocio is not None
    assert result.contato.nome == 'Maria TDD'
    assert result.negocio.stage == 'suplica'
    assert float(result.negocio.valor) == 1500.00


@pytest.mark.django_db
def test_lead_service_atribui_responsavel(tenant_aurora, usuario_operacional):
    """GREEN: LeadService deve atribuir responsavel ao negocio."""
    from recepcao.views.lead_service import LeadService, LeadData

    service = LeadService()
    dados = LeadData(nome='Joao', stage='prefeito')

    result = service.criar_lead(
        dados,
        tenant_id=tenant_aurora.id,
        usuario_id=usuario_operacional.id,
    )

    assert result.negocio.responsavel_id == usuario_operacional.id


@pytest.mark.django_db
def test_lead_service_campos_opcionais_vazios(tenant_aurora):
    """GREEN: LeadService deve aceitar campos opcionais vazios."""
    from recepcao.views.lead_service import LeadService, LeadData

    service = LeadService()
    dados = LeadData(nome='Simples', stage='suplica')

    result = service.criar_lead(dados, tenant_id=tenant_aurora.id)

    assert result.contato.tel == '—'
    assert result.contato.email == '—'
    assert result.contato.origem == '—'


# --- Testes de parse_lead_data ---

def test_parse_lead_data_normaliza_campos():
    """RED: parse_lead_data deve normalizar strings."""
    from recepcao.views.lead_service import parse_lead_data

    dados = parse_lead_data({
        'nome': '  Maria  ',
        'tel': '(11) 99999-0000',
        'email': ' MARIA@TDD.COM ',
        'origem': 'Instagram',
        'stage': 'suplica',
        'valor': '1.500,00',
    })

    assert dados.nome == 'Maria'
    assert dados.email == 'maria@tdd.com'
    assert dados.valor == Decimal('1500.00')


def test_parse_lead_data_valor_invalido():
    """RED: parse_lead_data deve retornar 0 para valor invalido."""
    from recepcao.views.lead_service import parse_lead_data

    dados = parse_lead_data({'nome': 'Teste', 'valor': 'abc'})

    assert dados.valor == Decimal(0)


def test_parse_lead_data_campos_ausentes():
    """RED: parse_lead_data deve tratar campos ausentes."""
    from recepcao.views.lead_service import parse_lead_data

    dados = parse_lead_data({'nome': 'Minimo'})

    assert dados.nome == 'Minimo'
    assert dados.tel == ''
    assert dados.email == ''
    assert dados.stage == ''
    assert dados.valor == Decimal(0)
