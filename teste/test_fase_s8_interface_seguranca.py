"""Testes da Fase S8 — revisão de interface e segurança.

Cobre as correções da S8:
- views de campos personalizados agora exigem login (bug de autenticação);
- botões migrados para o design system (hazon-btn-primary / hazon-btn-danger);
- ALLOWED_HOSTS configurável por ambiente (anti host-header spoofing);
- listagem de sessões ativas filtra as expiradas.
"""
import pytest
from django.test import Client
from django.utils import timezone

SENHA = 'senha123'


def _cliente_web(usuario):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s['nicho'] = ''
    s.save()
    return c


# ---------------------------------------------------------------------------
# S8.3 — Campos personalizados: exigem login (bug de autenticação corrigido)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_anonimo_nao_acessa_campos_sem_login(tenant_aurora):
    from contatos.models import CampoPersonalizado

    campo = CampoPersonalizado.objects.create(nome='CNPJ', tipo='texto', tenant=tenant_aurora)
    urls = ('/contatos/campos/',
            f'/contatos/campos/{campo.id}/editar/',
            f'/contatos/campos/{campo.id}/excluir/')
    for url in urls:
        r = Client().get(url)
        assert r.status_code == 302, url
        assert 'login' in r.url, url


@pytest.mark.django_db
def test_anonimo_nao_exclui_campo_sem_login(tenant_aurora):
    from contatos.models import CampoPersonalizado

    campo = CampoPersonalizado.objects.create(nome='CNPJ', tipo='texto', tenant=tenant_aurora)
    r = Client().post(f'/contatos/campos/{campo.id}/excluir/')
    assert r.status_code == 302
    assert CampoPersonalizado.objects.filter(pk=campo.id).exists()  # não excluiu


@pytest.mark.django_db
def test_admin_acessa_campos(admin_company, tenant_aurora):
    from contatos.models import CampoPersonalizado

    CampoPersonalizado.objects.create(nome='CNPJ', tipo='texto', tenant=tenant_aurora)
    c = _cliente_web(admin_company)
    r = c.get('/contatos/campos/')
    assert r.status_code == 200
    assert 'CNPJ' in r.content.decode()


@pytest.mark.django_db
def test_operacional_nao_edita_campo(tenant_aurora, usuario_operacional):
    from contatos.models import CampoPersonalizado

    campo = CampoPersonalizado.objects.create(nome='CNPJ', tipo='texto', tenant=tenant_aurora)
    c = _cliente_web(usuario_operacional)
    r = c.get(f'/contatos/campos/{campo.id}/editar/')
    assert r.status_code == 302  # volta para o dashboard (não é admin)


# ---------------------------------------------------------------------------
# S8.1 — Botões padronizados no design system
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_botao_novo_contato_usando_design_system(admin_company, tenant_aurora):
    from contatos.models import Contato

    Contato.objects.create(nome='Ana', seg='', tenant=tenant_aurora)
    c = _cliente_web(admin_company)
    html = c.get('/contatos/').content.decode()
    assert 'hazon-btn hazon-btn-primary' in html


@pytest.mark.django_db
def test_botao_excluir_usa_hazon_btn_danger(admin_company, tenant_aurora):
    from contatos.models import Contato

    contato = Contato.objects.create(nome='Ana', seg='', tenant=tenant_aurora)
    c = _cliente_web(admin_company)
    html = c.get(f'/contatos/{contato.id}/excluir/').content.decode()
    assert 'hazon-btn-danger' in html


@pytest.mark.django_db
def test_confirmacao_exclusao_campo_usa_hazon_btn_danger(admin_company, tenant_aurora):
    from contatos.models import CampoPersonalizado

    campo = CampoPersonalizado.objects.create(nome='CNPJ', tipo='texto', tenant=tenant_aurora)
    c = _cliente_web(admin_company)
    html = c.get(f'/contatos/campos/{campo.id}/excluir/').content.decode()
    assert 'hazon-btn-danger' in html


# ---------------------------------------------------------------------------
# S8.3 — ALLOWED_HOSTS configurável por ambiente
# ---------------------------------------------------------------------------

def test_allowed_hosts_default_liberado_no_dev():
    from django.conf import settings

    assert '*' in settings.ALLOWED_HOSTS


def test_allowed_hosts_parseia_lista_com_virgulas(monkeypatch):
    """A regra de parsing: DJANGO_ALLOWED_HOSTS com vírgulas vira uma lista."""
    import importlib

    import core.settings as settings_mod

    monkeypatch.setenv('DJANGO_ALLOWED_HOSTS', 'app.empresa.com.br,www.empresa.com.br')
    settings_mod = importlib.reload(settings_mod)
    assert settings_mod.ALLOWED_HOSTS == ['app.empresa.com.br', 'www.empresa.com.br']
    monkeypatch.delenv('DJANGO_ALLOWED_HOSTS', raising=False)
    settings_mod = importlib.reload(settings_mod)
    assert settings_mod.ALLOWED_HOSTS == ['*']  # dev sem variável: tudo liberado


def test_allowed_hosts_falha_fechado_fora_do_debug(monkeypatch):
    """S8 — sem variável e com DEBUG=0, não aceita host arbitrário (anti spoofing)."""
    import importlib

    import core.settings as settings_mod

    monkeypatch.delenv('DJANGO_ALLOWED_HOSTS', raising=False)
    monkeypatch.setenv('DJANGO_DEBUG', '0')  # reload relê o DEBUG do ambiente
    settings_mod = importlib.reload(settings_mod)
    assert '*' not in settings_mod.ALLOWED_HOSTS
    assert 'localhost' in settings_mod.ALLOWED_HOSTS
    monkeypatch.delenv('DJANGO_DEBUG', raising=False)
    settings_mod = importlib.reload(settings_mod)  # restaura para os demais testes


# ---------------------------------------------------------------------------
# S8.3 — Sessões ativas: expiradas são filtradas
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_sessoes_expiradas_sao_filtradas(admin_company):
    from django.contrib.sessions.backends.db import SessionStore
    from django.contrib.sessions.models import Session

    from acesso.views import _sessoes_do_usuario

    Session.objects.all().delete()  # limpa sessões residuais de outros testes

    def criar_sessao(usuario_id, minutos_restantes):
        s = SessionStore()
        s['usuario_id'] = usuario_id
        s['dispositivo'] = 'Chrome'
        s.save()
        expira = timezone.now() + timezone.timedelta(minutes=minutos_restantes)
        Session.objects.filter(session_key=s.session_key).update(expire_date=expira)
        return s.session_key

    criar_sessao(admin_company.id, -10)  # expirada → deve ser filtrada
    chave_ativa = criar_sessao(admin_company.id, 60)

    itens = _sessoes_do_usuario(admin_company.id, chave_ativa)
    assert len(itens) == 1
    assert itens[0]['key'] == chave_ativa
    assert itens[0]['atual'] is True
