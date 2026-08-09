"""Testes do papel viewer (somente leitura) — web, API e convite."""

import pytest
from django.contrib.auth.hashers import check_password
from django.test import Client
from django.utils import timezone
from datetime import timedelta

from acesso.models import Convite, Usuario
from contatos.models import Contato, Nota, criar_negocio


def _cliente_web(usuario):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s['nicho'] = 'saude'
    s.save()
    return c


def _contato_com_negocio(nome, tenant, stage='interessado', valor=100):
    contato = Contato.objects.create(nome=nome, seg='', tenant=tenant)
    criar_negocio(contato, stage=stage, valor=valor, tenant_id=tenant.id)
    return contato


# --- Leitura liberada ---

@pytest.mark.django_db
def test_viewer_ve_paginas_de_leitura(tenant_aurora, usuario_viewer):
    contato = _contato_com_negocio('Ana', tenant_aurora)
    c = _cliente_web(usuario_viewer)
    for url in ['/dashboard/', '/funil/', '/contatos/', '/agenda/',
                f'/contatos/{contato.id}/']:
        assert c.get(url).status_code == 200, url


# --- Escrita bloqueada na web ---

@pytest.mark.django_db
def test_viewer_nao_acessa_novo_contato(tenant_aurora, usuario_viewer):
    c = _cliente_web(usuario_viewer)
    r = c.get('/contatos/novo/')
    assert r.status_code == 302
    assert r.url == '/dashboard/'


def _dados_edicao(nome):
    return {
        'nome': nome, 'empresa': 'Empresa X', 'tel': '(11) 99999-0000', 'email': 'x@x.com',
        'seg': 'estetica', 'stage': 'fechado', 'valor': '0',
        'origem': 'Google', 'pagamento': 'Particular',
        'procedimento': 'Laser', 'ultima_consulta': '2026-01-01',
    }


@pytest.mark.django_db
def test_viewer_nao_edita_contato(tenant_aurora, usuario_viewer):
    contato = _contato_com_negocio('Ana', tenant_aurora)
    c = _cliente_web(usuario_viewer)
    assert c.get(f'/contatos/{contato.id}/editar/').status_code == 302
    r = c.post(f'/contatos/{contato.id}/editar/', _dados_edicao('Hackeado'))
    assert r.status_code == 302
    contato.refresh_from_db()
    assert contato.nome == 'Ana'  # nada mudou


@pytest.mark.django_db
def test_viewer_nao_move_no_funil(tenant_aurora, usuario_viewer):
    contato = _contato_com_negocio('Ana', tenant_aurora)
    negocio = contato.negocio
    c = _cliente_web(usuario_viewer)
    # AJAX (drag & drop) → 403
    r = c.post(f'/funil/{negocio.id}/mover/', {'stage': 'fechado'},
               HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    assert r.status_code == 403
    # menu fallback → redirect
    r = c.post(f'/funil/{negocio.id}/mover/', {'stage': 'fechado'})
    assert r.status_code == 302
    negocio.refresh_from_db()
    assert negocio.stage == 'interessado'  # não moveu


@pytest.mark.django_db
def test_viewer_nao_cria_negocio(tenant_aurora, usuario_viewer):
    contato = _contato_com_negocio('Ana', tenant_aurora)
    c = _cliente_web(usuario_viewer)
    r = c.post(f'/contatos/{contato.id}/negocios/novo/', {
        'titulo': 'Deal X', 'stage': 'orcamento', 'valor': '100',
    })
    assert r.status_code == 302
    assert contato.negocios.count() == 1  # nada criado


@pytest.mark.django_db
def test_viewer_nao_importa(usuario_viewer):
    c = _cliente_web(usuario_viewer)
    assert c.get('/contatos/importar/').status_code == 302


@pytest.mark.django_db
def test_viewer_nao_adiciona_nota(tenant_aurora, usuario_viewer):
    contato = _contato_com_negocio('Ana', tenant_aurora)
    c = _cliente_web(usuario_viewer)
    c.post(f'/contatos/{contato.id}/notas/', {'texto': 'tentativa'})
    assert Nota.objects.count() == 0


# --- Interface escondida para o viewer ---

@pytest.mark.django_db
def test_viewer_nao_ve_botoes_de_edicao(tenant_aurora, usuario_viewer, usuario_operacional):
    _contato_com_negocio('Ana', tenant_aurora)

    c = _cliente_web(usuario_viewer)
    html = c.get('/contatos/').content.decode('utf-8')
    assert 'Novo contato' not in html
    assert 'Importar' not in html
    assert 'title="Editar"' not in html

    # kanban sem drag e sem menu de mover
    html = c.get('/funil/').content.decode('utf-8')
    assert 'draggable="true"' not in html
    assert 'name="stage"' not in html
    assert 'Somente leitura' in html

    # ficha sem ações de escrita
    contato = Contato.objects.get(nome='Ana')
    html = c.get(f'/contatos/{contato.id}/').content.decode('utf-8')
    assert 'Novo negócio' not in html
    assert 'Adicionar nota' not in html

    # operacional continua vendo tudo (regressão)
    c2 = _cliente_web(usuario_operacional)
    html = c2.get('/contatos/').content.decode('utf-8')
    assert 'Novo contato' in html and 'title="Editar"' in html
    html = c2.get('/funil/').content.decode('utf-8')
    assert 'draggable="true"' in html


@pytest.mark.django_db
def test_link_do_cartao_aponta_para_contato(tenant_aurora, usuario_operacional):
    """Regressão: o link do cartão no kanban vai para a ficha do CONTATO,
    enquanto o data-id guarda o id do NEGÓCIO (usado pelo mover)."""
    contato = _contato_com_negocio('Ana', tenant_aurora)
    c = _cliente_web(usuario_operacional)
    html = c.get('/funil/').content.decode('utf-8')
    assert f'href="/contatos/{contato.id}/"' in html
    assert f'data-id="{contato.negocio.id}"' in html


@pytest.mark.django_db
def test_admin_saas_continua_editando_na_web(tenant_aurora, admin_saas):
    """Regressão: admin_saas (dono da plataforma) não pode perder a edição na web."""
    contato = _contato_com_negocio('Ana', tenant_aurora)
    c = _cliente_web(admin_saas)
    r = c.post(f'/contatos/{contato.id}/editar/', _dados_edicao('Nome Novo'))
    assert r.status_code == 302
    contato.refresh_from_db()
    assert contato.nome == 'Nome Novo'
    assert contato.negocio.stage == 'fechado'


# --- Configurações: o viewer gerencia só a própria conta ---

@pytest.mark.django_db
def test_viewer_altera_perfil_senha_e_tema(tenant_aurora, usuario_viewer):
    c = _cliente_web(usuario_viewer)
    r = c.post('/config/', {'acao': 'perfil', 'nome': 'Laura Nova', 'email': 'viewer@aurora.com'})
    assert r.status_code == 200
    assert 'Perfil atualizado'.encode() in r.content
    r = c.post('/config/', {'acao': 'senha', 'senha_atual': 'senha123',
                            'nova_senha': 'nova456', 'confirma_senha': 'nova456'})
    assert 'Senha alterada'.encode() in r.content
    assert check_password('nova456', Usuario.objects.get(pk=usuario_viewer.id).senha)
    c.post('/config/tema/', {'tema': 'claro', 'voltar': '/config/'})
    assert c.session['tema'] == 'claro'


@pytest.mark.django_db
def test_viewer_nao_ve_equipe_no_config(tenant_aurora, usuario_viewer):
    c = _cliente_web(usuario_viewer)
    html = c.get('/config/').content.decode('utf-8')
    assert 'Convites pendentes' not in html
    assert 'id="equipe"' not in html


# --- API: leitura sim, escrita não ---

@pytest.mark.django_db(transaction=True)
def test_api_viewer_le_mas_nao_escreve(client, tenant_aurora, usuario_viewer, headers_viewer):
    contato = _contato_com_negocio('Ana', tenant_aurora)
    assert client.get('/api/v1/contatos', headers=headers_viewer).status_code == 200
    assert client.post('/api/v1/contatos', headers=headers_viewer, json={
        'nome': 'X', 'seg': 'estetica', 'stage': 'interessado',
    }).status_code == 403
    assert client.put(f'/api/v1/contatos/{contato.id}', headers=headers_viewer, json={
        'nome': 'X', 'seg': 'estetica', 'stage': 'interessado',
    }).status_code == 403
    assert client.patch(f'/api/v1/contatos/{contato.id}/stage', headers=headers_viewer,
                        json={'stage': 'fechado'}).status_code == 403
    assert client.delete(f'/api/v1/contatos/{contato.id}', headers=headers_viewer).status_code == 403
    contato.refresh_from_db()
    assert contato.negocio.stage == 'interessado'


@pytest.mark.django_db(transaction=True)
def test_api_admin_saas_cria_viewer(client, tenant_aurora, headers_admin_saas):
    resp = client.post('/api/v1/usuarios', headers=headers_admin_saas, json={
        'nome': 'Laura Leitura', 'email': 'laura2@aurora.com', 'senha': 'senha1234',
        'role': 'viewer', 'tenant_id': tenant_aurora.id,
    })
    assert resp.status_code == 201
    assert resp.json()['role'] == 'viewer'


# --- Convite com papel viewer ---

@pytest.mark.django_db
def test_convite_viewer_aceite_cria_role_viewer(tenant_aurora, admin_company):
    c = _cliente_web(admin_company)
    r = c.post('/config/', {'acao': 'equipe', 'email': 'leitora@aurora.com', 'papel': 'viewer'})
    assert r.status_code == 302
    convite = Convite.objects.get(email='leitora@aurora.com')
    assert convite.papel == 'viewer'

    c2 = Client()
    r = c2.post(f'/convidar/{convite.token}/', {
        'nome': 'Leitora', 'senha': 'minha123', 'confirma': 'minha123',
    })
    assert r.status_code == 302
    u = Usuario.objects.get(email='leitora@aurora.com')
    assert u.role == 'viewer'
    assert u.tenant_id == tenant_aurora.id
