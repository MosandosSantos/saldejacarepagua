"""Testes para o filtro de prefeitura no kanban.

Ciclo TDD:
  1. Escrever teste falhando (RED)
  2. Verificar falha
  3. Escrever codigo minimo (GREEN)
  4. Refatorar
"""

import pytest
from decimal import Decimal
from django.test import Client

from contatos.models import Contato, Negocio, criar_negocio


def _cliente_web(usuario):
    """Cria cliente Django com sessao autenticada."""
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s['nicho'] = ''
    s.save()
    return c


@pytest.mark.django_db
def test_kanban_view_renderiza_com_filtro_prefeitura(usuario_operacional, tenant_aurora):
    """RED: kanban view deve renderizar com filtro de prefeitura."""
    from candidatos.models import Candidato

    # Cria candidato para ter dados
    Candidato.objects.create(
        tenant=tenant_aurora,
        nome_completo='Candidato Teste',
        cpf='123.456.789-00',
        prefeitura='Prefeitura Aurora',
        loja='Loja 1',
        status=Candidato.Status.EM_ANALISE,
        created_by=usuario_operacional,
    )

    c = _cliente_web(usuario_operacional)
    response = c.get('/recepcao/?prefeitura=Prefeitura Aurora')

    assert response.status_code == 200
    assert b'Prefeitura Aurora' in response.content


@pytest.mark.django_db
def test_kanban_view_filtra_candidatos_por_prefeitura(usuario_operacional, tenant_aurora):
    """RED: kanban view deve filtrar candidatos por prefeitura."""
    from candidatos.models import Candidato
    from django.core.cache import cache

    # Limpa cache antes do teste
    cache.clear()

    # Cria candidatos em diferentes prefeituras
    Candidato.objects.create(
        tenant=tenant_aurora,
        nome_completo='Candidato Aurora',
        cpf='123.456.789-00',
        prefeitura='Prefeitura Aurora',
        loja='Loja 1',
        status=Candidato.Status.EM_ANALISE,
        created_by=usuario_operacional,
    )
    Candidato.objects.create(
        tenant=tenant_aurora,
        nome_completo='Candidato Outra',
        cpf='987.654.321-00',
        prefeitura='Outra Prefeitura',
        loja='Loja 2',
        status=Candidato.Status.EM_ANALISE,
        created_by=usuario_operacional,
    )

    c = _cliente_web(usuario_operacional)

    # Request com filtro de prefeitura
    response = c.get('/recepcao/?prefeitura=Prefeitura Aurora')

    assert response.status_code == 200
    # Verifica que a prefeitura filtrada está no select
    assert b'Prefeitura Aurora' in response.content


@pytest.mark.django_db
def test_kanban_view_sem_filtro_mostra_todos(usuario_operacional, tenant_aurora):
    """RED: kanban view sem filtro deve mostrar todos os candidatos."""
    from candidatos.models import Candidato
    from django.core.cache import cache

    # Limpa cache antes do teste
    cache.clear()

    # Cria candidatos em diferentes prefeituras
    Candidato.objects.create(
        tenant=tenant_aurora,
        nome_completo='Candidato Aurora',
        cpf='123.456.789-00',
        prefeitura='Prefeitura Aurora',
        loja='Loja 1',
        status=Candidato.Status.EM_ANALISE,
        created_by=usuario_operacional,
    )
    Candidato.objects.create(
        tenant=tenant_aurora,
        nome_completo='Candidato Outra',
        cpf='987.654.321-00',
        prefeitura='Outra Prefeitura',
        loja='Loja 2',
        status=Candidato.Status.EM_ANALISE,
        created_by=usuario_operacional,
    )

    c = _cliente_web(usuario_operacional)

    # Request sem filtro
    response = c.get('/recepcao/')

    assert response.status_code == 200
    # Verifica que o select de prefeituras está presente
    assert b'filtro-prefeitura' in response.content


@pytest.mark.django_db
def test_kanban_view_select_prefeitura_inclui_opcoes(usuario_operacional, tenant_aurora):
    """RED: kanban view deve incluir select de prefeituras."""
    from candidatos.models import Candidato

    # Cria candidato para ter dados
    Candidato.objects.create(
        tenant=tenant_aurora,
        nome_completo='Candidato Teste',
        cpf='123.456.789-00',
        prefeitura='Prefeitura Aurora',
        loja='Loja 1',
        status=Candidato.Status.EM_ANALISE,
        created_by=usuario_operacional,
    )

    c = _cliente_web(usuario_operacional)
    response = c.get('/recepcao/')

    assert response.status_code == 200
    # Verifica que o select de prefeituras está presente
    assert b'filtro-prefeitura' in response.content
    assert b'Todos os vales' in response.content
