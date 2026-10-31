"""Testes do login web (Spec 001 — Problema Autenticação).

Cobre: login Django local, login inválido, usuário inexistente,
rate limit (5 falhas → 6ª bloqueada mesmo com senha correta) e
espelho local `usuarios` criado no primeiro login GPRB (mockado).
"""
from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from acesso.models import Usuario

def test_monte_libano_substitui_supremo_com_google_street_view():
    from django.template.loader import render_to_string
    from django.test import RequestFactory

    html = render_to_string('acesso/login.html', {
        'request': RequestFactory().get('/login/'),
        'agenda': {'ano': 2026, 'mes': 11, 'mes_nome': 'Novembro'},
    })
    assert 'id="sessao-monte-libano"' in html
    assert 'Loja Maçônica Monte Líbano' in html
    assert 'Rua Alexandre Rodrigues, 451' in html
    assert 'Vila Nova · Nova Iguaçu · Rio de Janeiro · Brasil' in html
    assert 'output=svembed' not in html
    assert 'monte-fachada' not in html
    # Mapa de como chegar: embed de rotas + botão oficial de direções.
    assert 'title="Mapa de como chegar à Loja Maçônica Monte Líbano no Google Maps"' in html
    assert 'maps/embed' in html
    assert 'https://www.google.com/maps/dir/?api=1&destination=-22.762325%2C-43.42937' in html
    assert 'Como chegar' in html
    assert 'id="monte-pausar"' not in html
    assert 'maps/api/js' not in html
    from django.conf import settings
    assert 'https://www.google.com' in settings.CSP_DIRETIVAS['frame-src']
    assert 'Supremo Conselho do Brasil do Grau 33º' not in html
    assert 'secretaria@sc33.org.br' not in html
    assert 'href="#sessao-monte-libano"' not in html  # menu flutuante removido da tela de login


SENHA = 'senha123'
CADASTRO_NUMERO = 777
EMAIL_IRMAO = 'irmao.cadastro@aurora.com'


def _criar_membro_com_conta(tenant_aurora, *, email=EMAIL_IRMAO):
    """Membro com número de cadastro + conta vinculada (login por número de cadastro)."""
    from contatos.models import Membro

    Usuario.objects.filter(email=email).delete()
    Membro.objects.filter(cadastro_numero=CADASTRO_NUMERO).delete()
    membro = Membro.objects.create(
        tenant=tenant_aurora, nome='Irmão Cadastro', email=email,
        situacao='ATIVO', cadastro_numero=CADASTRO_NUMERO,
    )
    usuario = Usuario.objects.create(
        nome='Irmão Cadastro', email=email, role='operacional',
        tenant=tenant_aurora, senha=make_password(SENHA), membro=membro,
    )
    return membro, usuario


@pytest.mark.django_db(transaction=True)
def test_login_django_ok_abre_sessao(usuario_operacional):
    c = Client()
    resp = c.post('/login/', {'email': 'oper@aurora.com', 'senha': SENHA})
    assert resp.status_code == 302  # redirect ao dashboard
    assert c.session.get('usuario_id') == usuario_operacional.id
    assert c.session.get('origem') == 'crm'


@pytest.mark.django_db(transaction=True)
def test_login_com_sessao_redireciona_dashboard(usuario_operacional):
    c = Client()
    c.post('/login/', {'email': 'oper@aurora.com', 'senha': SENHA})
    resp = c.get('/login/')
    assert resp.status_code == 302  # já logado → dashboard


@pytest.mark.django_db(transaction=True)
def test_login_senha_invalida(usuario_operacional):
    c = Client()
    resp = c.post('/login/', {'email': 'oper@aurora.com', 'senha': 'errada!123'})
    assert resp.status_code == 200  # re-render com erro
    assert c.session.get('usuario_id') is None


@pytest.mark.django_db(transaction=True)
def test_login_usuario_inexistente():
    c = Client()
    resp = c.post('/login/', {'email': 'fantasma@nenhum.com', 'senha': 'x1234567'})
    assert resp.status_code == 200
    assert c.session.get('usuario_id') is None


@pytest.mark.django_db(transaction=True)
@override_settings(RATE_LIMIT_ATIVO=True, LOGIN_RATE_LIMITE=5, LOGIN_RATE_JANELA=900)
def test_rate_limit_6a_tentativa_bloqueada(usuario_operacional):
    cache.clear()
    try:
        c = Client()
        # 5 falhas de senha esgotam as tentativas do par (ip, login)
        for _ in range(5):
            c.post('/login/', {'email': 'oper@aurora.com', 'senha': 'errada!123'})
        # 6ª tentativa — mesmo com SENHA CORRETA — é bloqueada
        resp = c.post('/login/', {'email': 'oper@aurora.com', 'senha': SENHA})
        assert resp.status_code == 200  # re-render do form
        assert 'Muitas tentativas' in resp.content.decode('utf-8')
        assert c.session.get('usuario_id') is None
        # após limpar o contador, o login volta a funcionar
        cache.clear()
        resp = c.post('/login/', {'email': 'oper@aurora.com', 'senha': SENHA})
        assert resp.status_code == 302
    finally:
        cache.clear()


@pytest.mark.django_db(transaction=True)
def test_espelho_usuarios_criado_no_login_gprb():
    """Login GPRB (mockado) cria espelho local em `usuarios` com papel mapeado."""
    from acesso.views import auth as auth_views

    cache.clear()
    Usuario.objects.filter(email='grao@britanea.com').delete()
    fake_gprb_user = {
        'id': 'uuid-fake-0001',
        'name': 'Grão-Mestre Teste',
        'email': 'grao@britanea.com',
        'loginIdentifier': '21999990000',
        'role': 'MEMBER',  # mapeado para 'viewer'
    }
    with patch.object(
        auth_views, 'gprb_autenticar_seguro',
        return_value=(fake_gprb_user, True),
    ):
        c = Client()
        resp = c.post('/login/', {'identifier': 'grao@britanea.com', 'senha': 'segredo!123'})
        assert resp.status_code == 302  # dashboard
        espelho = Usuario.objects.filter(email='grao@britanea.com').first()
        assert espelho is not None  # espelho criado
        assert espelho.nome == 'Grão-Mestre Teste'
        assert espelho.role == 'viewer'
        assert espelho.tenant is not None  # tenant GPRB local
        assert c.session.get('origem') == 'gprb'
        assert c.session.get('usuario_id') == espelho.id
    # limpeza: não poluir outros testes
    Usuario.objects.filter(email='grao@britanea.com').delete()


@pytest.mark.django_db(transaction=True)
def test_espelho_gprb_reusa_usuario_existente(usuario_operacional):
    """Se o espelho já existe, login GPRB não duplica — atualiza papel/tenant."""
    from acesso.views import auth as auth_views

    cache.clear()
    total_antes = Usuario.objects.filter(email='oper@aurora.com').count()
    fake_gprb_user = {
        'id': 'uuid-fake-0002',
        'name': 'Oper Aurora',
        'email': 'oper@aurora.com',
        'loginIdentifier': '21999888000',
        'role': 'MEMBER',
    }
    with patch.object(
        auth_views, 'gprb_autenticar_seguro',
        return_value=(fake_gprb_user, True),
    ):
        c = Client()
        resp = c.post('/login/', {'email': 'oper@aurora.com', 'senha': SENHA})
        assert resp.status_code == 302
    assert Usuario.objects.filter(email='oper@aurora.com').count() == total_antes


@pytest.mark.django_db(transaction=True)
def test_login_por_cadastro_numero_abre_sessao(tenant_aurora):
    _criar_membro_com_conta(tenant_aurora)
    cache.clear()
    try:
        c = Client()
        resp = c.post('/login/', {'identifier': str(CADASTRO_NUMERO), 'senha': SENHA})
        assert resp.status_code == 302  # redirect ao dashboard
        assert c.session.get('usuario_id') == Usuario.objects.get(email=EMAIL_IRMAO).id
        assert c.session.get('origem') == 'crm'
    finally:
        Usuario.objects.filter(email=EMAIL_IRMAO).delete()


@pytest.mark.django_db(transaction=True)
def test_login_por_cadastro_da_conta_admin(tenant_aurora):
    """Contas sem membro (admin_saas) entram pelo cadastro_numero próprio."""
    email_admin = 'admin.cadastro@saas.test'
    Usuario.objects.filter(email=email_admin).delete()
    admin = Usuario.objects.create(
        nome='Admin SaaS', email=email_admin, role='admin_saas', tenant=None,
        senha=make_password(SENHA), cadastro_numero=98593,
    )
    cache.clear()
    try:
        c = Client()
        resp = c.post('/login/', {'identifier': '98593', 'senha': SENHA})
        assert resp.status_code == 302  # dashboard
        assert c.session.get('usuario_id') == admin.id
    finally:
        Usuario.objects.filter(email=email_admin).delete()


@pytest.mark.django_db(transaction=True)
def test_login_por_cadastro_da_conta_senha_errada(tenant_aurora):
    email_admin = 'admin.cadastro@saas.test'
    Usuario.objects.filter(email=email_admin).delete()
    Usuario.objects.create(
        nome='Admin SaaS', email=email_admin, role='admin_saas', tenant=None,
        senha=make_password(SENHA), cadastro_numero=98593,
    )
    cache.clear()
    try:
        c = Client()
        resp = c.post('/login/', {'identifier': '98593', 'senha': 'errada!123'})
        assert resp.status_code == 200
        assert 'Login ou senha inválidos.' in resp.content.decode('utf-8')
        assert c.session.get('usuario_id') is None
    finally:
        Usuario.objects.filter(email=email_admin).delete()


@pytest.mark.django_db(transaction=True)
def test_login_email_bloqueado_para_conta_com_membro(tenant_aurora):
    """Conta vinculada a membro entra pelo número do cadastro — e-mail não abre sessão."""
    _criar_membro_com_conta(tenant_aurora)
    cache.clear()
    try:
        c = Client()
        resp = c.post('/login/', {'identifier': EMAIL_IRMAO, 'senha': SENHA})
        assert resp.status_code == 200
        assert 'Login ou senha inválidos.' in resp.content.decode('utf-8')
        assert c.session.get('usuario_id') is None
    finally:
        Usuario.objects.filter(email=EMAIL_IRMAO).delete()


@pytest.mark.django_db(transaction=True)
def test_login_por_cadastro_numero_senha_invalida(tenant_aurora):
    _criar_membro_com_conta(tenant_aurora)
    cache.clear()
    try:
        c = Client()
        resp = c.post('/login/', {'identifier': str(CADASTRO_NUMERO), 'senha': 'errada!123'})
        assert resp.status_code == 200
        assert 'Login ou senha inválidos.' in resp.content.decode('utf-8')
        assert c.session.get('usuario_id') is None
    finally:
        Usuario.objects.filter(email=EMAIL_IRMAO).delete()


@pytest.mark.django_db(transaction=True)
def test_login_por_cadastro_numero_membro_sem_conta(tenant_aurora):
    """Membro com número de cadastro mas sem conta ligada — senha checa em hash dummy."""
    from contatos.models import Membro

    Membro.objects.filter(cadastro_numero=666).delete()
    Membro.objects.create(
        tenant=tenant_aurora, nome='Irmão Sem Conta', email='solto666@example.test',
        situacao='ATIVO', cadastro_numero=666,
    )
    cache.clear()
    c = Client()
    resp = c.post('/login/', {'identifier': '666', 'senha': 'qualquer123'})
    assert resp.status_code == 200
    assert 'Login ou senha inválidos.' in resp.content.decode('utf-8')
    assert c.session.get('usuario_id') is None


@pytest.mark.django_db(transaction=True)
def test_login_por_cadastro_numero_inexistente():
    cache.clear()
    c = Client()
    resp = c.post('/login/', {'identifier': '987654', 'senha': SENHA})
    assert resp.status_code == 200
    assert 'Login ou senha inválidos.' in resp.content.decode('utf-8')
    assert c.session.get('usuario_id') is None


@pytest.mark.django_db
def test_login_labels_mostram_cadastro():
    html = Client().get('/login/').content.decode('utf-8')

    assert 'Cadastro' in html
    assert 'Celular' not in html


@pytest.mark.django_db
def test_login_shows_amorio_brand():
    response = Client().get('/login/')

    assert response.status_code == 200
    html = response.content.decode('utf-8')
    assert 'SAL DO REAA' in html
    assert '/static/img/logo' in html


@pytest.mark.django_db
def test_logout_shows_confirmation_after_session_flush(usuario_operacional):
    client = Client()
    session = client.session
    session['usuario_id'] = usuario_operacional.id
    session['usuario'] = {
        'nome': usuario_operacional.nome,
        'email': usuario_operacional.email,
        'role': usuario_operacional.role,
        'tenant_id': usuario_operacional.tenant_id,
    }
    session.save()

    response = client.post(reverse('acesso:logout'))

    assert response.status_code == 302
    assert response.url == reverse('acesso:login')
    assert client.session.get('usuario_id') is None
    login = client.get(response.url)
    assert 'Você saiu da conta SAL DO REAA.' in login.content.decode('utf-8')


@pytest.mark.django_db
def test_login_shows_turnstile_carmine_button_and_forgot_link():
    response = Client().get('/login/')
    html = response.content.decode('utf-8')

    assert response.status_code == 200
    assert 'class="cf-turnstile"' in html
    assert 'data-sitekey=' in html
    assert 'LOGIN' in html
    assert 'Entrar no painel' not in html
    assert '#991b1b' in html
    assert 'Esqueci a senha' in html
    assert 'id="toggleSenha"' in html


@pytest.mark.django_db
def test_login_rejects_failed_turnstile_before_authentication(usuario_operacional, monkeypatch):
    from acesso.views import auth as auth_views

    monkeypatch.setattr(auth_views, 'verify_turnstile_token', lambda _token: False, raising=False)
    client = Client()
    response = client.post('/login/', {
        'email': 'oper@aurora.com',
        'senha': SENHA,
        'cf-turnstile-response': 'invalid-token',
    })

    assert response.status_code == 200
    assert 'Confirme que você é humano' in response.content.decode('utf-8')
    assert client.session.get('usuario_id') is None


@pytest.mark.django_db
@override_settings(
    CLOUDFLARE_TURNSTILE_CONFIGURED=False,
    CLOUDFLARE_TURNSTILE_SITE_KEY='',
    CLOUDFLARE_TURNSTILE_SECRET_KEY='',
)
def test_login_fails_closed_without_turnstile_configuration(usuario_operacional):
    client = Client()
    response = client.post('/login/', {'email': 'oper@aurora.com', 'senha': SENHA})

    assert response.status_code == 200
    assert 'Verificação humana indisponível' in response.content.decode('utf-8')
    assert client.session.get('usuario_id') is None


@pytest.mark.django_db
@override_settings(
    CLOUDFLARE_TURNSTILE_CONFIGURED=True,
    CLOUDFLARE_TURNSTILE_SITE_KEY='public-site-key',
    CLOUDFLARE_TURNSTILE_SECRET_KEY='private-secret-key',
)
def test_login_exposes_site_key_but_never_secret():
    html = Client().get('/login/').content.decode('utf-8')

    assert 'data-sitekey="public-site-key"' in html
    assert 'private-secret-key' not in html


@pytest.mark.django_db
@override_settings(
    CLOUDFLARE_TURNSTILE_CONFIGURED=False,
    CLOUDFLARE_TURNSTILE_SITE_KEY='',
    CLOUDFLARE_TURNSTILE_SECRET_KEY='',
)
def test_login_disables_submit_when_turnstile_is_unconfigured():
    html = Client().get('/login/').content.decode('utf-8')

    assert 'Verificação humana indisponível' in html
    assert 'type="submit"' in html
    assert 'disabled' in html


@pytest.mark.django_db
def test_login_agenda_tem_tres_vistas_filtro_exportacao_e_mapa_historico():
    response = Client().get('/login/')
    html = response.content.decode('utf-8')
    agenda_html = html[html.index('<section id="sessao-calendario"'):]

    assert response.status_code == 200
    assert 'data-agenda-modo="calendario"' in agenda_html
    assert 'data-agenda-modo="kanban"' in agenda_html
    assert 'data-agenda-modo="lista"' in agenda_html
    assert 'id="agenda-loja"' in agenda_html
    assert 'data-data=' in agenda_html
    assert 'John Rocque' in agenda_html and '1746' in agenda_html
    assert 'agenda/exportar/' in agenda_html
    assert '<script>' in agenda_html[agenda_html.index('data-agenda-modo="calendario"'):agenda_html.index('<!-- SUPREMO')]


@pytest.mark.django_db
def test_agenda_sem_eventos_mostra_exemplos_identificados_no_kanban_e_lista():
    response = Client().get('/login/?ano=2026&mes=11')
    html = response.content.decode('utf-8')
    agenda_html = html[html.index('<section id="sessao-calendario"'):html.index('<!-- SUPREMO')]
    kanban = agenda_html[agenda_html.index('id="agenda-visao-kanban"'):agenda_html.index('id="agenda-visao-lista"')]
    lista = agenda_html[agenda_html.index('id="agenda-visao-lista"'):agenda_html.index('id="agenda-vazio"')]

    assert response.status_code == 200
    assert 'Demonstração — sessão fictícia' in kanban
    assert 'Demonstração — sessão fictícia' in lista
    assert 'não representa evento confirmado' in agenda_html
    assert 'data-demo="true"' in kanban
    assert 'data-demo="true"' in lista
    assert 'Demonstração — sessão fictícia' not in agenda_html[agenda_html.index('id="agenda-visao-calendario"'):agenda_html.index('id="agenda-visao-kanban"')]


@pytest.mark.django_db
def test_agenda_publica_exibe_calendario_e_kanban_diario_com_loja_oculta(tenant_aurora):
    from contatos.models import Loja, Vale
    from tarefas.models import Evento

    Vale.objects.get_or_create(tenant=tenant_aurora, defaults={'nome': 'Vale Teste', 'sigla': f'T{uuid4().hex[:8]}'})
    loja = Loja.objects.create(tenant=tenant_aurora, nome='Loja Confidencial')
    inicio = timezone.make_aware(datetime(2026, 11, 10, 19, 0))
    Evento.objects.create(
        titulo='Sessão Pública', descricao='Descrição reservada', tipo='sessao',
        data_inicio=inicio, data_fim=inicio + timedelta(hours=2), loja_id=str(loja.pk),
    )

    response = Client().get('/login/?ano=2026&mes=11')
    html = response.content.decode('utf-8')
    agenda_html = html[html.index('<section id="sessao-calendario"'):]

    assert response.status_code == 200
    assert agenda_html.count('Sessão Pública') == 3
    assert 'Sessão' in agenda_html
    assert 'Loja 1' in agenda_html
    assert 'Loja Confidencial' not in agenda_html
    assert 'Descrição reservada' not in agenda_html
    assert agenda_html.count('data-loja="loja-1"') == 3
    assert 'data-data="2026-11-10"' in agenda_html


@pytest.mark.django_db
def test_exportacao_agenda_publica_filtra_mes_e_loja_sem_dados_privados(tenant_aurora):
    from contatos.models import Loja, Vale
    from tarefas.models import Evento

    Vale.objects.get_or_create(tenant=tenant_aurora, defaults={'nome': 'Vale Teste', 'sigla': f'E{uuid4().hex[:8]}'})
    loja = Loja.objects.create(tenant=tenant_aurora, nome='Loja Confidencial')
    inicio = timezone.make_aware(datetime(2026, 11, 10, 19, 0))
    Evento.objects.create(
        titulo='Evento a Exportar', descricao='Não exportar descrição', tipo='sessao',
        data_inicio=inicio, data_fim=inicio + timedelta(hours=2), loja_id=str(loja.pk),
    )
    Evento.objects.create(
        titulo='Outro Mês', descricao='', tipo='sessao',
        data_inicio=timezone.make_aware(datetime(2026, 12, 10, 19, 0)),
        data_fim=timezone.make_aware(datetime(2026, 12, 10, 21, 0)), loja_id=str(loja.pk),
    )

    page = Client().get('/login/?ano=2026&mes=11').content.decode('utf-8')
    agenda_html = page[page.index('<section id="sessao-calendario"'):page.index('<!-- SUPREMO')]
    import re
    loja_publica = re.search(
        r'data-loja="(loja-\d+)"><span class="agenda-evento-hora">[^<]*</span>Evento a Exportar',
        agenda_html,
    ).group(1)
    assert loja_publica != str(loja.pk)
    response = Client().get(f'/login/agenda/exportar/?ano=2026&mes=11&loja={loja_publica}')
    ics = response.content.decode('utf-8')

    assert response.status_code == 200
    assert response['Content-Type'].startswith('text/calendar')
    assert 'SUMMARY:Evento a Exportar' in ics
    assert 'Outro Mês' not in ics
    assert 'Loja Confidencial' not in ics
    assert 'Não exportar descrição' not in ics
    assert 'DTSTART:20261110T190000' in ics
    assert 'DTEND:20261110T210000' in ics

