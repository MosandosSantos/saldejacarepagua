"""Testes TDD para view de cadastro rapido de lead."""
import pytest
from django.test import Client
from contatos.models import Contato, Negocio


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
def test_novo_lead_requer_login():
    """RED: novo_lead deve redirecionar para login se nao autenticado."""
    c = Client()
    response = c.post('/recepcao/novo-lead/')
    assert response.status_code in (302, 403)


@pytest.mark.django_db
def test_novo_lead_requer_post(usuario_operacional):
    """RED: novo_lead deve aceitar apenas POST."""
    c = _cliente_web(usuario_operacional)
    response = c.get('/recepcao/novo-lead/')
    assert response.status_code == 400


@pytest.mark.django_db
def test_novo_lead_cria_contato_e_negocio(usuario_operacional, tenant_aurora):
    """GREEN: novo_lead deve criar contato e negocio."""
    c = _cliente_web(usuario_operacional)
    
    dados = {
        'nome': 'Lead Teste',
        'empresa': 'Empresa Teste',
        'telefone': '11999998888',
        'email': 'lead@teste.com',
        'valor': '1500',
        'origem': 'Outro',
        'stage': 'suplica',
    }
    
    response = c.post('/recepcao/novo-lead/', dados)
    
    assert response.status_code == 200
    data = response.json()
    assert data['ok'] is True
    assert 'html' in data
    
    # Verifica se criou contato e negocio
    assert Contato.objects.filter(nome='Lead Teste', tenant=tenant_aurora).exists()
    assert Negocio.objects.filter(
        contato__nome='Lead Teste',
        stage='suplica'
    ).exists()


@pytest.mark.django_db
def test_novo_lead_rejeita_nome_vazio(usuario_operacional, tenant_aurora):
    """RED: novo_lead deve rejeitar nome vazio."""
    c = _cliente_web(usuario_operacional)
    
    dados = {
        'nome': '',
        'empresa': 'Empresa Teste',
        'stage': 'suplica',
    }
    
    response = c.post('/recepcao/novo-lead/', dados)
    
    assert response.status_code == 400
    data = response.json()
    assert data['ok'] is False
    assert 'erros' in data


@pytest.mark.django_db
def test_novo_lead_rejeita_stage_invalido(usuario_operacional, tenant_aurora):
    """RED: novo_lead deve rejeitar stage invalido."""
    c = _cliente_web(usuario_operacional)
    
    dados = {
        'nome': 'Lead Teste',
        'stage': 'stage_inexistente',
    }
    
    response = c.post('/recepcao/novo-lead/', dados)
    
    assert response.status_code == 400
    data = response.json()
    assert data['ok'] is False


@pytest.mark.django_db
def test_novo_lead_valor_invalido(usuario_operacional, tenant_aurora):
    """RED: novo_lead deve tratar valor invalido."""
    c = _cliente_web(usuario_operacional)
    
    dados = {
        'nome': 'Lead Teste',
        'valor': 'abc',
        'stage': 'suplica',
    }
    
    response = c.post('/recepcao/novo-lead/', dados)
    
    # Deve aceitar e ignorar valor invalido
    assert response.status_code == 200
    data = response.json()
    assert data['ok'] is True


@pytest.mark.django_db
def test_novo_lead_campos_opcionais_vazios(usuario_operacional, tenant_aurora):
    """GREEN: novo_lead deve aceitar campos opcionais vazios."""
    c = _cliente_web(usuario_operacional)
    
    dados = {
        'nome': 'Lead Teste',
        'stage': 'suplica',
    }
    
    response = c.post('/recepcao/novo-lead/', dados)
    
    assert response.status_code == 200
    data = response.json()
    assert data['ok'] is True


@pytest.mark.django_db
def test_novo_lead_atribui_responsavel(usuario_operacional, tenant_aurora):
    """GREEN: novo_lead deve atribuir responsavel ao negocio."""
    c = _cliente_web(usuario_operacional)
    
    dados = {
        'nome': 'Lead Responsavel',
        'stage': 'suplica',
    }
    
    response = c.post('/recepcao/novo-lead/', dados)
    
    assert response.status_code == 200
    
    # Verifica se o negocio tem responsavel
    negocio = Negocio.objects.get(contato__nome='Lead Responsavel')
    assert negocio.responsavel_id == usuario_operacional.id
