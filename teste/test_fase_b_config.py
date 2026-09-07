"""Testes da Fase B — configurações (perfil, senha, tema, sessões) e convite por link."""

from datetime import timedelta

import pytest
from django.contrib.auth.hashers import check_password
from django.test import Client
from django.utils import timezone

from acesso.models import Convite, Usuario


def _cliente_web(usuario):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s['nicho'] = 'saude'
    s.save()
    return c


# --- Acesso à página de configurações ---

@pytest.mark.django_db
def test_operacional_acessa_config_sem_equipe(usuario_operacional):
    c = _cliente_web(usuario_operacional)
    r = c.get('/config/')
    assert r.status_code == 200
    html = r.content.decode()
    assert 'Usuários' in html
    assert 'id="perfil"' in html
    assert 'Convites pendentes' not in html  # equipe/convites só para admin


@pytest.mark.django_db
def test_operacional_nao_convida(tenant_aurora, usuario_operacional):
    c = _cliente_web(usuario_operacional)
    c.post('/config/', {'acao': 'equipe', 'email': 'novo@aurora.com', 'papel': 'operacional'})
    assert not Convite.objects.filter(email='novo@aurora.com').exists()
    assert not Usuario.objects.filter(email='novo@aurora.com').exists()


@pytest.mark.django_db
def test_nao_logado_redireciona_para_login():
    r = Client().get('/config/')
    assert r.status_code == 302
    assert '/login/' in r.url


# --- Perfil ---

@pytest.mark.django_db
def test_perfil_atualiza_nome_e_email(usuario_operacional):
    c = _cliente_web(usuario_operacional)
    r = c.post('/config/', {'acao': 'perfil', 'nome': 'Oper Novo', 'email': 'novo@aurora.com'})
    assert r.status_code == 200
    u = Usuario.objects.get(pk=usuario_operacional.id)
    assert u.nome == 'Oper Novo'
    assert u.email == 'novo@aurora.com'
    assert c.session['usuario']['nome'] == 'Oper Novo'  # header atualizado


@pytest.mark.django_db
def test_perfil_email_duplicado_rejeitado(usuario_operacional, admin_company):
    c = _cliente_web(usuario_operacional)
    r = c.post('/config/', {'acao': 'perfil', 'nome': 'Oper', 'email': admin_company.email})
    assert 'Já existe um usuário'.encode() in r.content
    assert Usuario.objects.get(pk=usuario_operacional.id).email == usuario_operacional.email


# --- Senha ---

@pytest.mark.django_db
def test_altera_senha_com_atual_correta(usuario_operacional):
    c = _cliente_web(usuario_operacional)
    r = c.post('/config/', {'acao': 'senha', 'senha_atual': 'senha123',
                            'nova_senha': 'nova4567', 'confirma_senha': 'nova4567'})
    assert r.status_code == 200
    assert b'Senha alterada' in r.content
    u = Usuario.objects.get(pk=usuario_operacional.id)
    assert check_password('nova4567', u.senha)


@pytest.mark.django_db
def test_altera_senha_atual_errada_rejeitada(usuario_operacional):
    c = _cliente_web(usuario_operacional)
    r = c.post('/config/', {'acao': 'senha', 'senha_atual': 'errada',
                            'nova_senha': 'nova4567', 'confirma_senha': 'nova4567'})
    assert b'incorreta' in r.content
    assert check_password('senha123', Usuario.objects.get(pk=usuario_operacional.id).senha)


@pytest.mark.django_db
def test_altera_senha_curta_rejeitada(usuario_operacional):
    c = _cliente_web(usuario_operacional)
    r = c.post('/config/', {'acao': 'senha', 'senha_atual': 'senha123',
                            'nova_senha': '123', 'confirma_senha': '123'})
    assert b'pelo menos 8 caracteres' in r.content


# --- Sessões ativas ---

@pytest.mark.django_db
def test_encerra_sessao_remota(usuario_operacional):
    c1 = _cliente_web(usuario_operacional)
    c2 = _cliente_web(usuario_operacional)  # segunda sessão no "outro aparelho"
    chave_outra = c2.session.session_key
    assert chave_outra is not None and chave_outra != c1.session.session_key

    r = c1.post('/config/', {'acao': 'sessao', 'sessao_key': chave_outra})
    assert r.status_code == 200
    assert 'Sessão encerrada'.encode() in r.content

    from django.contrib.sessions.models import Session
    assert not Session.objects.filter(session_key=chave_outra).exists()
    assert Session.objects.filter(session_key=c1.session.session_key).exists()  # atual intacta


# --- Convite por link ---

@pytest.mark.django_db
def test_admin_cria_convite_e_gera_link(tenant_aurora, admin_company):
    c = _cliente_web(admin_company)
    r = c.post('/config/', {'acao': 'equipe', 'email': 'nova@aurora.com', 'papel': 'operacional'})
    assert r.status_code == 302
    convite = Convite.objects.get(email='nova@aurora.com')
    assert convite.tenant_id == tenant_aurora.id
    assert convite.papel == 'operacional'
    assert convite.pendente
    assert convite.expira_em > timezone.now()

    # página de config recém-redirecionada mostra o link
    r2 = c.get(f'/config/?convite={convite.id}')
    assert convite.token in r2.content.decode()


@pytest.mark.django_db
def test_convite_email_ja_em_uso_rejeitado(admin_company, usuario_operacional):
    c = _cliente_web(admin_company)
    r = c.post('/config/', {'acao': 'equipe', 'email': usuario_operacional.email, 'papel': 'operacional'})
    assert 'Já existe um usuário'.encode() in r.content
    assert not Convite.objects.exists()


@pytest.mark.django_db
def test_convite_duplicado_pendente_rejeitado(tenant_aurora, admin_company):
    Convite.objects.create(
        token='token-1', tenant=tenant_aurora, email='x@aurora.com',
        papel='operacional', criado_por=admin_company,
        expira_em=timezone.now() + timedelta(days=7),
    )
    c = _cliente_web(admin_company)
    r = c.post('/config/', {'acao': 'equipe', 'email': 'X@aurora.com', 'papel': 'operacional'})
    assert b'convite pendente' in r.content
    assert Convite.objects.count() == 1


@pytest.mark.django_db
def test_aceite_de_convite_cria_usuario_e_entra(tenant_aurora, admin_company):
    convite = Convite.objects.create(
        token='token-aceite', tenant=tenant_aurora, email='ana@aurora.com',
        papel='operacional', criado_por=admin_company,
        expira_em=timezone.now() + timedelta(days=7),
    )
    r = Client().get('/convidar/token-aceite/')
    assert r.status_code == 200
    assert 'ana@aurora.com' in r.content.decode()

    c = Client()
    r = c.post('/convidar/token-aceite/', {
        'nome': 'Ana Souza', 'senha': 'minha123', 'confirma': 'minha123',
    })
    assert r.status_code == 302  # entra direto no painel
    u = Usuario.objects.get(email='ana@aurora.com')
    assert u.role == 'operacional'
    assert u.tenant_id == tenant_aurora.id
    assert check_password('minha123', u.senha)
    convite.refresh_from_db()
    assert convite.usado_em is not None
    assert convite.usado_por_id == u.id
    assert c.session['usuario_id'] == u.id


@pytest.mark.django_db
def test_convite_expirado_invalido(tenant_aurora, admin_company):
    Convite.objects.create(
        token='token-exp', tenant=tenant_aurora, email='ana@aurora.com',
        papel='operacional', criado_por=admin_company,
        expira_em=timezone.now() - timedelta(days=1),
    )
    r = Client().get('/convidar/token-exp/')
    assert r.status_code == 200
    assert b'expirou' in r.content
    assert not Usuario.objects.filter(email='ana@aurora.com').exists()


@pytest.mark.django_db
def test_convite_cancelado_pelo_admin(tenant_aurora, admin_company):
    convite = Convite.objects.create(
        token='token-cancel', tenant=tenant_aurora, email='ana@aurora.com',
        papel='operacional', criado_por=admin_company,
        expira_em=timezone.now() + timedelta(days=7),
    )
    c = _cliente_web(admin_company)
    c.post('/config/', {'acao': 'convite_cancelar', 'convite_id': convite.id})
    convite.refresh_from_db()
    assert convite.cancelado_em is not None
    r = Client().get('/convidar/token-cancel/')
    assert b'cancelado' in r.content


@pytest.mark.django_db
def test_convite_token_desconhecido(admin_company):
    r = Client().get('/convidar/token-inexistente/')
    assert r.status_code == 200
    assert 'Convite não encontrado'.encode() in r.content


# --- Tema claro/escuro ---

@pytest.mark.django_db
def test_tema_alterna_e_persiste_na_sessao(usuario_operacional):
    c = _cliente_web(usuario_operacional)
    r = c.post('/config/tema/', {'tema': 'claro', 'voltar': '/recepcao/'})
    assert r.status_code == 302
    assert r.url == '/recepcao/'
    assert c.session['tema'] == 'claro'

    r = c.get('/recepcao/')
    assert 'data-tema="claro"' in r.content.decode()


@pytest.mark.django_db
def test_tema_padrao_escuro(usuario_operacional):
    c = _cliente_web(usuario_operacional)
    r = c.get('/config/')
    assert 'data-tema="escuro"' in r.content.decode()


@pytest.mark.django_db
def test_tema_claro_nao_vaza_para_pagina_publica(tenant_aurora, admin_company):
    # admin em tema claro clica no próprio link de convite (mesma sessão)
    c = _cliente_web(admin_company)
    c.post('/config/tema/', {'tema': 'claro', 'voltar': '/config/'})
    assert c.session['tema'] == 'claro'
    Convite.objects.create(
        token='token-pub', tenant=tenant_aurora, email='pub@aurora.com',
        papel='operacional', criado_por=admin_company,
        expira_em=timezone.now() + timedelta(days=7),
    )
    r = Client().get('/convidar/token-pub/')  # navegador/sessão pública
    assert r.status_code == 200
    assert 'data-tema="escuro"' in r.content.decode()  # pública é sempre escura


@pytest.mark.django_db
def test_cancelar_convite_sem_id_nao_quebra(admin_company):
    c = _cliente_web(admin_company)
    r = c.post('/config/', {'acao': 'convite_cancelar'})  # sem convite_id
    assert r.status_code == 200
