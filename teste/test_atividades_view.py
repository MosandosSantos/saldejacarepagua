"""Testes TDD para view de criacao de atividades."""
import pytest
from datetime import date, time
from django.test import Client
from contatos.models import Contato
from tarefas.models import Tarefa


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
def test_nova_atividade_requer_login():
    """RED: nova_atividade deve redirecionar para login se nao autenticado."""
    c = Client()
    response = c.post('/recepcao/nova-atividade/')
    assert response.status_code in (302, 403)


@pytest.mark.django_db
def test_nova_atividade_requer_post(usuario_operacional):
    """RED: nova_atividade deve aceitar apenas POST."""
    c = _cliente_web(usuario_operacional)
    response = c.get('/recepcao/nova-atividade/')
    assert response.status_code == 400


@pytest.mark.django_db
def test_nova_atividade_requer_titulo(usuario_operacional):
    """RED: nova_atividade deve exigir titulo."""
    c = _cliente_web(usuario_operacional)
    
    dados = {
        'titulo': '',
        'prioridade': 'media',
    }
    
    response = c.post('/recepcao/nova-atividade/', dados)
    
    assert response.status_code == 400
    data = response.json()
    assert data['ok'] is False


@pytest.mark.django_db
def test_nova_atividade_prioridade_invalida(usuario_operacional):
    """RED: nova_atividade deve rejeitar prioridade invalida."""
    c = _cliente_web(usuario_operacional)
    
    dados = {
        'titulo': 'Atividade Teste',
        'prioridade': 'invalida',
    }
    
    response = c.post('/recepcao/nova-atividade/', dados)
    
    assert response.status_code == 400
    data = response.json()
    assert data['ok'] is False


@pytest.mark.django_db
def test_nova_atividade_cria_tarefa(usuario_operacional, tenant_aurora):
    """GREEN: nova_atividade deve criar tarefa."""
    c = _cliente_web(usuario_operacional)
    
    dados = {
        'titulo': 'Atividade Teste',
        'prioridade': 'media',
    }
    
    response = c.post('/recepcao/nova-atividade/', dados)
    
    assert response.status_code == 200
    data = response.json()
    assert data['ok'] is True
    
    # Verifica se criou a tarefa
    assert Tarefa.objects.filter(
        titulo='Atividade Teste',
        tenant=tenant_aurora
    ).exists()


@pytest.mark.django_db
def test_nova_atividade_com_vencimento(usuario_operacional, tenant_aurora):
    """GREEN: nova_atividade deve aceitar vencimento."""
    c = _cliente_web(usuario_operacional)
    
    dados = {
        'titulo': 'Atividade com Vencimento',
        'prioridade': 'alta',
        'vencimento': '2026-12-31',
    }
    
    response = c.post('/recepcao/nova-atividade/', dados)
    
    assert response.status_code == 200
    
    tarefa = Tarefa.objects.get(titulo='Atividade com Vencimento')
    assert tarefa.vencimento == date(2026, 12, 31)


@pytest.mark.django_db
def test_nova_atividade_com_hora(usuario_operacional, tenant_aurora):
    """GREEN: nova_atividade deve aceitar hora."""
    c = _cliente_web(usuario_operacional)
    
    dados = {
        'titulo': 'Atividade com Hora',
        'prioridade': 'media',
        'hora': '14:30',
    }
    
    response = c.post('/recepcao/nova-atividade/', dados)
    
    assert response.status_code == 200
    
    tarefa = Tarefa.objects.get(titulo='Atividade com Hora')
    assert tarefa.hora == time(14, 30)


@pytest.mark.django_db
def test_nova_atividade_hora_invalida(usuario_operacional):
    """RED: nova_atividade deve rejeitar hora invalida."""
    c = _cliente_web(usuario_operacional)
    
    dados = {
        'titulo': 'Atividade Hora Invalida',
        'prioridade': 'media',
        'hora': 'abc',
    }
    
    response = c.post('/recepcao/nova-atividade/', dados)
    
    assert response.status_code == 400
    data = response.json()
    assert data['ok'] is False


@pytest.mark.django_db
def test_nova_atividade_data_invalida(usuario_operacional):
    """RED: nova_atividade deve rejeitar data invalida."""
    c = _cliente_web(usuario_operacional)
    
    dados = {
        'titulo': 'Atividade Data Invalida',
        'prioridade': 'media',
        'vencimento': 'abc',
    }
    
    response = c.post('/recepcao/nova-atividade/', dados)
    
    assert response.status_code == 400
    data = response.json()
    assert data['ok'] is False


@pytest.mark.django_db
def test_nova_atividade_vincula_contato(usuario_operacional, tenant_aurora):
    """GREEN: nova_atividade deve vincular a contato."""
    c = _cliente_web(usuario_operacional)
    
    contato = Contato.objects.create(nome='Contato Atividade', tenant=tenant_aurora)
    
    dados = {
        'titulo': 'Atividade com Contato',
        'prioridade': 'media',
        'contato_id': str(contato.id),
    }
    
    response = c.post('/recepcao/nova-atividade/', dados)
    
    assert response.status_code == 200
    
    tarefa = Tarefa.objects.get(titulo='Atividade com Contato')
    assert tarefa.contato_id == contato.id


@pytest.mark.django_db
def test_nova_atividade_contato_invalido(usuario_operacional, tenant_aurora):
    """RED: nova_atividade deve tratar contato invalido."""
    c = _cliente_web(usuario_operacional)
    
    dados = {
        'titulo': 'Atividade Contato Invalido',
        'prioridade': 'media',
        'contato_id': '99999',
    }
    
    response = c.post('/recepcao/nova-atividade/', dados)
    
    # Deve aceitar mesmo sem contato
    assert response.status_code == 200


@pytest.mark.django_db
def test_nova_atividade_atribui_responsavel(usuario_operacional, tenant_aurora):
    """GREEN: nova_atividade deve atribuir responsavel."""
    c = _cliente_web(usuario_operacional)
    
    dados = {
        'titulo': 'Atividade Responsavel',
        'prioridade': 'media',
    }
    
    response = c.post('/recepcao/nova-atividade/', dados)
    
    assert response.status_code == 200
    
    tarefa = Tarefa.objects.get(titulo='Atividade Responsavel')
    assert tarefa.responsavel_id == usuario_operacional.id
