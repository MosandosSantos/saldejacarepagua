"""Testes da Fase O — S4 do PRD HAZON (e-mail avançado).

Rastreio de cliques (4.3.5): links do corpo reescritos para o endpoint público
/emails/clique/<token>/<codigo>/ que registra o clique e redireciona.
Conversão de propostas (4.3.6): quando um negócio do contato fecha, os e-mails
do contato ganham convertido_em (funil, formulário web e API).
"""

import pytest
from django.test import Client

from contatos.models import Contato, criar_negocio
from emails.models import EmailEnviado, ModeloEmail
from emails.servico import _encurtar_url, reescrever_links

SENHA = 'senha123'


def _cliente_web(usuario):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s['nicho'] = 'saude'
    s.save()
    return c


def _modelo(tenant_aurora, corpo=None):
    return ModeloEmail.objects.create(
        tenant=tenant_aurora,
        nome='Proposta',
        assunto='Proposta para {{nome}}',
        corpo=corpo or 'Olá {{nome}}, veja nossa proposta: <a href="https://exemplo.com/proposta">Abrir</a>',
    )


def _contato(tenant_aurora, email='ana@x.com'):
    return Contato.objects.create(
        nome='Ana', empresa='X', tel='(11) 98888-7777', email=email,
        seg='geral', tenant=tenant_aurora,
    )


def _envio(contato, modelo, status='simulado'):
    return EmailEnviado.objects.create(
        tenant=contato.tenant,
        contato=contato,
        modelo=modelo,
        assunto='Proposta para ' + contato.nome,
        corpo='corpo com <a href="https://exemplo.com/x">link</a>',
        destinatario=contato.email,
        status=status,
    )


# --- Reescrita de links ---

@pytest.mark.django_db
def test_reescreve_links_do_corpo():
    corpo = 'Veja: <a href="https://exemplo.com/proposta">Abrir</a> e <a href="/relativo">interno</a>'
    novo = reescrever_links(corpo, 'http://host/emails', 'abc')
    assert 'http://host/emails/clique/abc/' in novo
    assert 'exemplo.com/proposta' not in novo  # URL original saiu do href
    assert 'href="/relativo"' in novo  # link relativo intacto
    assert 'Abrir' in novo  # texto do link preservado


@pytest.mark.django_db
def test_nao_reescreve_mailto():
    corpo = '<a href="mailto:ana@x.com">mail</a>'
    assert reescrever_links(corpo, 'http://h', 't') == corpo


@pytest.mark.django_db
def test_url_roundtrip():
    url = 'https://exemplo.com/proposta?valor=1500&utm=1'
    codigo = _encurtar_url(url)
    from emails.servico import _expandir_url

    assert _expandir_url(codigo) == url


# --- Endpoint de clique ---

@pytest.mark.django_db
def test_clique_registra_e_redireciona(tenant_aurora):
    modelo = _modelo(tenant_aurora)
    contato = _contato(tenant_aurora)
    envio = _envio(contato, modelo)
    url = 'https://exemplo.com/proposta'
    r = Client().get(f'/emails/clique/{envio.token}/{_encurtar_url(url)}/')
    assert r.status_code == 302
    assert r.url == url
    envio.refresh_from_db()
    assert envio.cliques == 1
    assert envio.ultimo_clique_em is not None


@pytest.mark.django_db
def test_clique_acumula_contagem(tenant_aurora):
    modelo = _modelo(tenant_aurora)
    contato = _contato(tenant_aurora)
    envio = _envio(contato, modelo)
    url = 'https://exemplo.com/proposta'
    for _ in range(3):
        Client().get(f'/emails/clique/{envio.token}/{_encurtar_url(url)}/')
    envio.refresh_from_db()
    assert envio.cliques == 3


@pytest.mark.django_db
def test_ultimo_clique_atualiza_a_cada_clique(tenant_aurora):
    from datetime import timedelta

    from django.utils import timezone

    modelo = _modelo(tenant_aurora)
    contato = _contato(tenant_aurora)
    envio = _envio(contato, modelo)
    url = 'https://exemplo.com/proposta'
    primeiro = timezone.now() - timedelta(hours=1)
    envio.ultimo_clique_em = primeiro
    envio.cliques = 1
    envio.save(update_fields=['ultimo_clique_em', 'cliques'])
    Client().get(f'/emails/clique/{envio.token}/{_encurtar_url(url)}/')
    envio.refresh_from_db()
    assert envio.cliques == 2
    assert envio.ultimo_clique_em > primeiro  # atualizou no 2º clique também


@pytest.mark.django_db
def test_clique_token_inexistente_404():
    assert Client().get('/emails/clique/00000000-0000-0000-0000-000000000000/YWJj/').status_code == 404


@pytest.mark.django_db
def test_clique_url_invalida_404(tenant_aurora):
    modelo = _modelo(tenant_aurora)
    contato = _contato(tenant_aurora)
    envio = _envio(contato, modelo)
    assert Client().get(f'/emails/clique/{envio.token}/%%%invalid%%%/').status_code == 404


@pytest.mark.django_db
def test_clique_nao_permite_javascript(tenant_aurora):
    modelo = _modelo(tenant_aurora)
    contato = _contato(tenant_aurora)
    envio = _envio(contato, modelo)
    codigo = _encurtar_url('javascript:alert(1)')
    r = Client().get(f'/emails/clique/{envio.token}/{codigo}/')
    assert r.status_code == 404
    envio.refresh_from_db()
    assert envio.cliques == 0


@pytest.mark.django_db
def test_clique_sem_login_e_sem_csrf():
    # o endpoint é público (o destinatário clica) — sem sessão, sem CSRF
    r = Client().post('/emails/clique/00000000-0000-0000-0000-000000000000/YWJj/', {})
    assert r.status_code in (302, 404)


# --- Campanha reescreve links ---

@pytest.mark.django_db
def test_campanha_reescreve_links_no_corpo(tenant_aurora, admin_company):
    from emails.servico import disparar_campanha

    modelo = _modelo(tenant_aurora)
    contato = _contato(tenant_aurora)
    disparar_campanha(modelo, [contato], 'http://testserver/emails/aberto')
    envio = EmailEnviado.objects.get()
    assert '/clique/' in envio.corpo
    assert 'exemplo.com/proposta' not in envio.corpo
    assert 'emails/aberto/' in envio.corpo  # pixel de abertura continua


@pytest.mark.django_db
def test_campanha_envia_um_por_contato(tenant_aurora, admin_company):
    from emails.servico import disparar_campanha

    modelo = _modelo(tenant_aurora)
    c1 = _contato(tenant_aurora, email='c1@x.com')
    c2 = _contato(tenant_aurora, email='c2@x.com')
    disparar_campanha(modelo, [c1, c2], 'http://testserver/emails')
    assert EmailEnviado.objects.count() == 2


# --- Conversão de propostas ---

@pytest.mark.django_db
def test_fechar_no_funil_marca_conversao(tenant_aurora, admin_company):
    from recepcao.models import garantir_etapas

    garantir_etapas(tenant_aurora.id, 'saude')
    modelo = _modelo(tenant_aurora)
    contato = _contato(tenant_aurora)
    envio = _envio(contato, modelo)
    negocio = criar_negocio(contato, stage='interessado', tenant_id=tenant_aurora.id)
    c = _cliente_web(admin_company)
    r = c.post(f'/recepcao/{negocio.id}/mover/', {'stage': 'fechado'})
    assert r.status_code in (200, 302)  # redirect sem AJAX; JSON com X-Requested-With
    envio.refresh_from_db()
    assert envio.convertido_em is not None


@pytest.mark.django_db
def test_nao_marca_conversao_sem_fechamento(tenant_aurora, admin_company):
    modelo = _modelo(tenant_aurora)
    contato = _contato(tenant_aurora)
    envio = _envio(contato, modelo)
    negocio = criar_negocio(contato, stage='interessado', tenant_id=tenant_aurora.id)
    c = _cliente_web(admin_company)
    c.post(f'/recepcao/{negocio.id}/mover/', {'stage': 'orcamento'})
    envio.refresh_from_db()
    assert envio.convertido_em is None


@pytest.mark.django_db
def test_fechar_no_formulario_marca_conversao(tenant_aurora, admin_company):
    from recepcao.models import garantir_etapas

    garantir_etapas(tenant_aurora.id, 'saude')
    modelo = _modelo(tenant_aurora)
    contato = _contato(tenant_aurora)
    envio = _envio(contato, modelo)
    c = _cliente_web(admin_company)
    c.post(f'/contatos/{contato.id}/editar/', {
        'nome': 'Ana', 'empresa': 'X', 'tel': '(11) 98888-7777', 'email': 'ana@x.com',
        'seg': 'geral', 'stage': 'fechado', 'ultima_consulta': '2026-01-15',
        'procedimento': 'Laser',
    })
    envio.refresh_from_db()
    assert envio.convertido_em is not None


@pytest.mark.django_db
def test_negocio_novo_em_fechado_marca_conversao(tenant_aurora, admin_company):
    from recepcao.models import garantir_etapas

    garantir_etapas(tenant_aurora.id, 'saude')
    modelo = _modelo(tenant_aurora)
    contato = _contato(tenant_aurora)
    envio = _envio(contato, modelo)
    c = _cliente_web(admin_company)
    c.post(f'/contatos/{contato.id}/negocios/novo/', {
        'titulo': 'Deal fechado', 'stage': 'fechado', 'valor': '500',
    })
    envio.refresh_from_db()
    assert envio.convertido_em is not None


@pytest.mark.django_db
def test_fechar_negocio_no_formulario_marca_conversao(tenant_aurora, admin_company):
    from recepcao.models import garantir_etapas

    garantir_etapas(tenant_aurora.id, 'saude')
    modelo = _modelo(tenant_aurora)
    contato = _contato(tenant_aurora)
    envio = _envio(contato, modelo)
    negocio = criar_negocio(contato, stage='interessado', tenant_id=tenant_aurora.id)
    c = _cliente_web(admin_company)
    c.post(f'/contatos/{contato.id}/negocios/{negocio.id}/editar/', {
        'titulo': 'Deal', 'stage': 'fechado', 'valor': '500',
    })
    envio.refresh_from_db()
    assert envio.convertido_em is not None


# --- API ---

def _login(client, usuario):
    from teste.conftest import fazer_login

    return fazer_login(client, usuario.email)


@pytest.mark.django_db(transaction=True)
def test_api_fechar_marca_conversao(client, tenant_aurora, usuario_operacional):
    from recepcao.models import garantir_etapas

    garantir_etapas(tenant_aurora.id, 'saude')
    modelo = _modelo(tenant_aurora)
    headers = _login(client, usuario_operacional)
    r = client.post('/api/v1/contatos', json={
        'nome': 'Ana', 'seg': 'geral', 'stage': 'interessado',
    }, headers=headers)
    contato_id = r.json()['id']
    contato_api = Contato.objects.get(pk=contato_id)
    envio = _envio(contato_api, modelo)
    r = client.patch(f'/api/v1/contatos/{contato_id}/stage', headers=headers, json={'stage': 'fechado'})
    assert r.status_code == 200
    envio.refresh_from_db()
    assert envio.convertido_em is not None


@pytest.mark.django_db(transaction=True)
def test_api_atualizar_para_fechado_marca_conversao(client, tenant_aurora, usuario_operacional):
    from recepcao.models import garantir_etapas

    garantir_etapas(tenant_aurora.id, 'saude')
    modelo = _modelo(tenant_aurora)
    contato = _contato(tenant_aurora)
    envio = _envio(contato, modelo)
    headers = _login(client, usuario_operacional)
    r = client.put(f'/api/v1/contatos/{contato.id}', headers=headers, json={
        'nome': contato.nome, 'seg': 'geral', 'stage': 'fechado',
    })
    assert r.status_code == 200
    envio.refresh_from_db()
    assert envio.convertido_em is not None


# --- UI: KPIs na lista ---

@pytest.mark.django_db
def test_lista_mostra_kpis(tenant_aurora, admin_company):
    modelo = _modelo(tenant_aurora)
    c1 = _contato(tenant_aurora, email='c1@x.com')
    c2 = _contato(tenant_aurora, email='c2@x.com')
    e1 = _envio(c1, modelo)
    _envio(c2, modelo)
    # e1 foi aberto e clicado; e2 nada
    from django.utils import timezone

    e1.aberto_em = timezone.now()
    e1.cliques = 2
    e1.save(update_fields=['aberto_em', 'cliques'])
    html = _cliente_web(admin_company).get('/emails/').content.decode()
    assert 'Enviados' in html and 'Abertos' in html and 'Cliques' in html and 'Convertidos' in html
    assert '2' in html  # total de envios
    assert 'c1@x.com' in html  # histórico mostra o destinatário


@pytest.mark.django_db
def test_lista_mostra_conversao_no_historico(tenant_aurora, admin_company):
    from django.utils import timezone

    modelo = _modelo(tenant_aurora)
    contato = _contato(tenant_aurora)
    envio = _envio(contato, modelo)
    envio.convertido_em = timezone.now()
    envio.save(update_fields=['convertido_em'])
    html = _cliente_web(admin_company).get('/emails/').content.decode()
    assert '✓' in html  # selo de conversão no histórico
