"""Testes TDD para ImportService — importacao de leads via CSV.

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
def test_import_service_rejeita_csv_sem_coluna_nome(tenant_aurora):
    """RED: ImportService deve rejeitar CSV sem coluna 'nome'."""
    from recepcao.views.import_service import ImportService, ImportValidationError

    service = ImportService()
    conteudo = 'telefone,email\n11999990000,teste@test.com'

    with pytest.raises(ImportValidationError) as exc_info:
        service.importar_csv(
            conteudo=conteudo,
            tenant_id=tenant_aurora.id,
            stage_map={'suplica': {'key': 'suplica'}},
            etapa_padrao='suplica',
        )

    assert 'nome' in str(exc_info.value.erros).lower()


@pytest.mark.django_db
def test_import_service_aceita_csv_vazio(tenant_aurora):
    """GREEN: ImportService deve aceitar CSV so com cabecalho."""
    from recepcao.views.import_service import ImportService

    service = ImportService()
    conteudo = 'nome,telefone,email'

    resultado = service.importar_csv(
        conteudo=conteudo,
        tenant_id=tenant_aurora.id,
        stage_map={'suplica': {'key': 'suplica'}},
        etapa_padrao='suplica',
    )

    assert resultado.criados == 0
    assert resultado.erros_linha == []


# --- Testes de criacao ---

@pytest.mark.django_db
def test_import_service_importa_leads_basicos(tenant_aurora):
    """GREEN: ImportService deve importar leads corretamente."""
    from recepcao.views.import_service import ImportService

    service = ImportService()
    conteudo = 'nome,telefone,email,valor\nMaria,11999990000,maria@test.com,1500\nJoao,11888880000,,2000'

    resultado = service.importar_csv(
        conteudo=conteudo,
        tenant_id=tenant_aurora.id,
        stage_map={'suplica': {'key': 'suplica'}},
        etapa_padrao='suplica',
    )

    assert resultado.criados == 2
    assert Contato.objects.filter(tenant_id=tenant_aurora.id).count() == 2


@pytest.mark.django_db
def test_import_service_usa_etapa_padrao(tenant_aurora):
    """GREEN: ImportService deve usar etapa padrao quando nao especificada."""
    from recepcao.views.import_service import ImportService

    service = ImportService()
    conteudo = 'nome\nLead Sem Etapa'

    resultado = service.importar_csv(
        conteudo=conteudo,
        tenant_id=tenant_aurora.id,
        stage_map={'suplica': {'key': 'suplica'}, 'prefeito': {'key': 'prefeito'}},
        etapa_padrao='suplica',
    )

    assert resultado.criados == 1
    negocio = Negocio.objects.filter(tenant_id=tenant_aurora.id).first()
    assert negocio.stage == 'suplica'


@pytest.mark.django_db
def test_import_service_trata_linha_nome_vazio(tenant_aurora):
    """GREEN: ImportService deve ignorar linhas com nome vazio."""
    from recepcao.views.import_service import ImportService

    service = ImportService()
    conteudo = 'nome,telefone\nMaria,11999990000\n,11888880000\nJoao,11777770000'

    resultado = service.importar_csv(
        conteudo=conteudo,
        tenant_id=tenant_aurora.id,
        stage_map={'suplica': {'key': 'suplica'}},
        etapa_padrao='suplica',
    )

    assert resultado.criados == 2
    assert len(resultado.erros_linha) == 1
    assert 'nome vazio' in resultado.erros_linha[0].lower()


@pytest.mark.django_db
def test_import_service_atribui_responsavel(tenant_aurora, usuario_operacional):
    """GREEN: ImportService deve atribuir responsavel aos leads."""
    from recepcao.views.import_service import ImportService

    service = ImportService()
    conteudo = 'nome\nLead Com Responsavel'

    resultado = service.importar_csv(
        conteudo=conteudo,
        tenant_id=tenant_aurora.id,
        stage_map={'suplica': {'key': 'suplica'}},
        etapa_padrao='suplica',
        usuario_id=usuario_operacional.id,
    )

    assert resultado.criados == 1
    negocio = Negocio.objects.filter(tenant_id=tenant_aurora.id).first()
    assert negocio.responsavel_id == usuario_operacional.id


@pytest.mark.django_db
def test_import_service_trata_valor_invalido(tenant_aurora):
    """GREEN: ImportService deve tratar valor invalido como 0."""
    from recepcao.views.import_service import ImportService

    service = ImportService()
    conteudo = 'nome,valor\nLead Valor Ruim,abc'

    resultado = service.importar_csv(
        conteudo=conteudo,
        tenant_id=tenant_aurora.id,
        stage_map={'suplica': {'key': 'suplica'}},
        etapa_padrao='suplica',
    )

    assert resultado.criados == 1
    negocio = Negocio.objects.filter(tenant_id=tenant_aurora.id).first()
    assert float(negocio.valor) == 0.0
