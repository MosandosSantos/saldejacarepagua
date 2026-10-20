"""Matriz RBAC web (Spec 005, T3).

Cobre papéis × rotas de escrita/gerenciamento do painel:
- viewer: bloqueado em escritas GPRB (302) e em equipe; consulta própria liberada.
- operacional: não gerencia equipe.
- admin_company: gerencia equipe.
"""
import pytest
from django.test import Client

SENHA = 'senha123'


def _login(email):
    c = Client()
    resp = c.post('/login/', {'email': email, 'senha': SENHA})
    assert resp.status_code == 302, f'login falhou para {email}'
    return c


@pytest.mark.django_db(transaction=True)
def test_viewer_bloqueado_em_escritas_de_potencias(usuario_viewer):
    c = _login('viewer@aurora.com')
    resp = c.post('/contatos/prefeitura/nova/', {'nome': 'Tentativa Viewer'})
    assert resp.status_code == 302
    assert resp['Location'].endswith('/dashboard/')  # bloqueio (sem referer)


@pytest.mark.django_db(transaction=True)
def test_viewer_bloqueado_em_escritas_de_lojas(usuario_viewer):
    c = _login('viewer@aurora.com')
    resp = c.post('/contatos/loja/nova/', {'nome': 'Tentativa Viewer'})
    assert resp.status_code == 302
    assert resp['Location'].endswith('/dashboard/')


@pytest.mark.django_db(transaction=True)
def test_viewer_bloqueado_na_equipe(usuario_viewer):
    c = _login('viewer@aurora.com')
    resp = c.get('/equipe/')
    assert resp.status_code == 302
    assert resp['Location'].endswith('/dashboard/')


@pytest.mark.django_db(transaction=True)
def test_viewer_ve_sua_config_em_modo_leitura(usuario_viewer):
    c = _login('viewer@aurora.com')
    resp = c.get('/config/')
    assert resp.status_code == 200  # consulta própria liberada


@pytest.mark.django_db(transaction=True)
def test_viewer_pode_editar_apenas_o_proprio_perfil(usuario_viewer):
    c = _login('viewer@aurora.com')
    resp = c.post('/config/', {'acao': 'perfil', 'nome': 'Laura Editada', 'email': 'viewer@aurora.com'})
    assert resp.status_code == 200
    usuario_viewer.refresh_from_db()
    assert usuario_viewer.nome == 'Laura Editada'


@pytest.mark.django_db(transaction=True)
def test_operacional_nao_gerencia_equipe(usuario_operacional):
    c = _login('oper@aurora.com')
    resp = c.get('/equipe/')
    assert resp.status_code == 302
    assert resp['Location'].endswith('/dashboard/')


@pytest.mark.django_db(transaction=True)
def test_admin_company_gerencia_equipe(admin_company):
    c = _login('dona@aurora.com')
    resp = c.get('/equipe/')
    assert resp.status_code == 200


@pytest.mark.django_db(transaction=True)
def test_operacional_pode_acessar_contatos(usuario_operacional):
    """Operacional tem permissão de edição — acessa as telas (conteúdo vazio/erro tratado)."""
    c = _login('oper@aurora.com')
    resp = c.get('/contatos/')
    assert resp.status_code == 200
