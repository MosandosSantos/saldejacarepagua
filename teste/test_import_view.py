"""Testes TDD para view de importacao de leads."""
import pytest
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
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


def _criar_csv(conteudo):
    """Cria um arquivo CSV para upload."""
    return SimpleUploadedFile(
        'leads.csv',
        conteudo.encode('utf-8'),
        content_type='text/csv'
    )


@pytest.mark.django_db
def test_importar_leads_requer_login():
    """RED: importar_leads deve redirecionar para login se nao autenticado."""
    c = Client()
    response = c.post('/recepcao/importar/')
    assert response.status_code in (302, 403)


@pytest.mark.django_db
def test_importar_leads_requer_post(usuario_operacional):
    """RED: importar_leads deve aceitar apenas POST."""
    c = _cliente_web(usuario_operacional)
    response = c.get('/recepcao/importar/')
    assert response.status_code == 400


@pytest.mark.django_db
def test_importar_leads_requer_arquivo(usuario_operacional):
    """RED: importar_leads deve exigir arquivo."""
    c = _cliente_web(usuario_operacional)
    response = c.post('/recepcao/importar/')
    assert response.status_code == 400
    data = response.json()
    assert data['ok'] is False


@pytest.mark.django_db
def test_importar_leads_csv_vazio(usuario_operacional, tenant_aurora):
    """GREEN: importar_leads deve aceitar CSV vazio."""
    c = _cliente_web(usuario_operacional)
    
    arquivo = _criar_csv('nome,empresa,telefone\n')
    response = c.post('/recepcao/importar/', {'arquivo': arquivo})
    
    assert response.status_code == 200
    data = response.json()
    assert data['ok'] is True
    assert data['criados'] == 0


@pytest.mark.django_db
def test_importar_leads_importa_dados_basicos(usuario_operacional, tenant_aurora):
    """GREEN: importar_leads deve importar leads do CSV."""
    c = _cliente_web(usuario_operacional)
    
    csv_content = 'nome,empresa,telefone\nLead 1,Empresa 1,11999998888\nLead 2,Empresa 2,11888887777\n'
    arquivo = _criar_csv(csv_content)
    
    response = c.post('/recepcao/importar/', {'arquivo': arquivo})
    
    assert response.status_code == 200
    data = response.json()
    assert data['ok'] is True
    assert data['criados'] == 2
    
    # Verifica se criou os contatos
    assert Contato.objects.filter(nome='Lead 1', tenant=tenant_aurora).exists()
    assert Contato.objects.filter(nome='Lead 2', tenant=tenant_aurora).exists()


@pytest.mark.django_db
def test_importar_leads_trata_linha_nome_vazio(usuario_operacional, tenant_aurora):
    """GREEN: importar_leads deve tratar linha com nome vazio."""
    c = _cliente_web(usuario_operacional)
    
    csv_content = 'nome,empresa\nLead 1,Empresa 1\n,Empresa 2\nLead 3,Empresa 3\n'
    arquivo = _criar_csv(csv_content)
    
    response = c.post('/recepcao/importar/', {'arquivo': arquivo})
    
    assert response.status_code == 200
    data = response.json()
    assert data['ok'] is True
    # Apenas 2 leads importados (linha 2 ignorada)
    assert data['criados'] == 2


@pytest.mark.django_db
def test_importar_leads_atribui_responsavel(usuario_operacional, tenant_aurora):
    """GREEN: importar_leads deve atribuir responsavel aos negocios."""
    c = _cliente_web(usuario_operacional)
    
    csv_content = 'nome,empresa\nLead Responsavel,Empresa R\n'
    arquivo = _criar_csv(csv_content)
    
    response = c.post('/recepcao/importar/', {'arquivo': arquivo})
    
    assert response.status_code == 200
    
    # Verifica se o negocio tem responsavel
    negocio = Negocio.objects.get(contato__nome='Lead Responsavel')
    assert negocio.responsavel_id == usuario_operacional.id


@pytest.mark.django_db
def test_importar_leads_etapa_padrao(usuario_operacional, tenant_aurora):
    """GREEN: importar_leads deve usar etapa padrao."""
    c = _cliente_web(usuario_operacional)
    
    csv_content = 'nome,empresa\nLead Padrao,Empresa P\n'
    arquivo = _criar_csv(csv_content)
    
    response = c.post('/recepcao/importar/', {'arquivo': arquivo})
    
    assert response.status_code == 200
    
    # Verifica se o negocio esta na etapa suplica (padrao)
    negocio = Negocio.objects.get(contato__nome='Lead Padrao')
    assert negocio.stage == 'suplica'


@pytest.mark.django_db
def test_importar_leads_trata_valor_invalido(usuario_operacional, tenant_aurora):
    """GREEN: importar_leads deve tratar valor invalido."""
    c = _cliente_web(usuario_operacional)
    
    csv_content = 'nome,empresa,valor\nLead Valor,Empresa V,abc\n'
    arquivo = _criar_csv(csv_content)
    
    response = c.post('/recepcao/importar/', {'arquivo': arquivo})
    
    # Deve aceitar e ignorar valor invalido
    assert response.status_code == 200
    data = response.json()
    assert data['ok'] is True
