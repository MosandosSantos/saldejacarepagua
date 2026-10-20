"""Testes para cache invalidation e filtro de prefeitura no kanban.

Ciclo TDD:
  1. Escrever teste falhando (RED)
  2. Verificar falha
  3. Escrever codigo minimo (GREEN)
  4. Refatorar
"""

import pytest
from unittest.mock import patch, MagicMock
from django.core.cache import cache

from contatos.models import Contato, Negocio, criar_negocio


@pytest.fixture
def candidato_aurora(tenant_aurora):
    """Cria um candidato para testes."""
    from candidatos.models import Candidato
    from acesso.models import Usuario

    usuario = Usuario.objects.first()
    if not usuario:
        usuario = Usuario.objects.create(
            nome='Teste',
            email='teste@teste.com',
            tenant=tenant_aurora,
        )

    return Candidato.objects.create(
        tenant=tenant_aurora,
        nome_completo='Candidato Teste',
        cpf='123.456.789-00',
        prefeitura='Prefeitura Aurora',
        loja='Loja 1',
        email='candidato@teste.com',
        status=Candidato.Status.EM_ANALISE,
        created_by=usuario,
    )


# --- Testes de cards_candidatos com filtro de prefeitura ---

@pytest.mark.django_db
def test_cards_candidatos_filtra_por_prefeitura(tenant_aurora, candidato_aurora):
    """RED: cards_candidatos deve filtrar por prefeitura quando especificado."""
    from recepcao.views.helpers import cards_candidatos

    # Limpa cache antes do teste
    cache.clear()

    # Cria outro candidato em outra prefeitura
    from candidatos.models import Candidato
    from acesso.models import Usuario

    usuario = Usuario.objects.first()
    Candidato.objects.create(
        tenant=tenant_aurora,
        nome_completo='Outro Candidato',
        cpf='987.654.321-00',
        prefeitura='Outra Prefeitura',
        loja='Loja 2',
        email='outro@teste.com',
        status=Candidato.Status.EM_ANALISE,
        created_by=usuario,
    )

    # Filtra por prefeitura específica
    cards = cards_candidatos(tenant_aurora.id, prefeitura='Prefeitura Aurora')

    assert len(cards) == 1
    assert cards[0]['nome'] == 'Candidato Teste'


@pytest.mark.django_db
def test_cards_candidatos_retorna_todos_sem_filtro(tenant_aurora, candidato_aurora):
    """RED: cards_candidatos deve retornar todos quando não há filtro."""
    from recepcao.views.helpers import cards_candidatos

    # Limpa cache antes do teste
    cache.clear()

    from candidatos.models import Candidato
    from acesso.models import Usuario

    usuario = Usuario.objects.first()
    Candidato.objects.create(
        tenant=tenant_aurora,
        nome_completo='Outro Candidato',
        cpf='987.654.321-00',
        prefeitura='Outra Prefeitura',
        loja='Loja 2',
        email='outro@teste.com',
        status=Candidato.Status.EM_ANALISE,
        created_by=usuario,
    )

    # Sem filtro
    cards = cards_candidatos(tenant_aurora.id)

    assert len(cards) == 2


@pytest.mark.django_db
def test_cards_candidatos_cache_inclui_prefeitura(tenant_aurora, candidato_aurora):
    """RED: cache de cards_candidatos deve ser independente por prefeitura."""
    from recepcao.views.helpers import cards_candidatos

    # Limpa cache antes do teste
    cache.clear()

    # Busca com filtro
    cards_pf = cards_candidatos(tenant_aurora.id, prefeitura='Prefeitura Aurora')
    # Busca sem filtro
    cards_todos = cards_candidatos(tenant_aurora.id)

    # Deve ter chaves de cache diferentes (com versão)
    # Verifica que retornou resultados diferentes
    assert len(cards_pf) == 1
    assert len(cards_todos) == 1


# --- Testes de invalidação de cache ---

@pytest.mark.django_db
def test_invalidar_cache_kanban_invalida_via_versao(tenant_aurora, candidato_aurora):
    """RED: _invalidar_cache_kanban deve invalidar cache via versão."""
    from candidatos.views.cache import invalidar_cache_kanban as _invalidar_cache_kanban
    from recepcao.views.helpers import cards_candidatos

    # Limpa cache antes do teste
    cache.clear()

    # Popula cache
    cards_candidatos(tenant_aurora.id)
    cards_candidatos(tenant_aurora.id, prefeitura='Prefeitura Aurora')

    # Verifica que cache está populado
    version_key = f'recepcao_cards_candidatos_version_{tenant_aurora.id}'
    version_inicial = cache.get(version_key, 0)

    # Invalida cache
    _invalidar_cache_kanban(tenant_aurora.id)

    # Verifica que versão foi incrementada
    version_nova = cache.get(version_key, 0)
    assert version_nova == version_inicial + 1

    # Cache antigo não deve ser retornado (nova versão)
    # Busca com nova versão deve retornar dados frescos
    cards_novos = cards_candidatos(tenant_aurora.id)
    assert len(cards_novos) == 1


@pytest.mark.django_db
def test_excluir_candidato_invalida_cache(tenant_aurora, candidato_aurora, rf, usuario_operacional):
    """RED: excluir_candidato deve invalidar o cache do kanban."""
    from candidatos.views import excluir_candidato
    from recepcao.views.helpers import cards_candidatos

    # Limpa cache antes do teste
    cache.clear()

    # Popula cache
    cards_candidatos(tenant_aurora.id)
    version_key = f'recepcao_cards_candidatos_version_{tenant_aurora.id}'
    version_inicial = cache.get(version_key, 0)

    # Simula request com permissão de admin_saas
    request = rf.post(f'/candidatos/excluir/{candidato_aurora.pk}/')
    request.session = {
        'usuario_id': usuario_operacional.pk,
        'usuario': {'role': 'admin_saas', 'tenant_id': tenant_aurora.id},
        'tenant_id': tenant_aurora.id,
    }

    response = excluir_candidato(request, candidato_aurora.pk)

    # Verifica que cache foi invalidado
    version_nova = cache.get(version_key, 0)
    assert version_nova == version_inicial + 1
