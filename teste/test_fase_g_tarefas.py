"""Testes da Fase G — Tarefas & lembretes (follow-ups).

Cada clínica tem suas tarefas (título, contato, responsável, prioridade e
vencimento); o vencimento alimenta os lembretes (atrasadas/hoje/próximas),
o badge do header e o alerta do dashboard.
"""

from datetime import date, timedelta

import pytest
from django.test import Client

from contatos.models import Contato
from tarefas.models import Tarefa


def _cliente_web(usuario):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s['nicho'] = 'saude'
    s.save()
    return c


def _tarefa(tenant, titulo='Ligar de volta', **kw):
    return Tarefa.objects.create(tenant=tenant, titulo=titulo, **kw)


def _contato(tenant, nome='Ana'):
    return Contato.objects.create(nome=nome, seg='estetica', tenant=tenant, origem='Indicacao')


# --- CRUD básico ---

@pytest.mark.django_db
def test_cria_tarefa_pela_lista(tenant_aurora, admin_company, usuario_operacional):
    c = _cliente_web(admin_company)
    r = c.post('/tarefas/', {
        'acao': 'criar', 'titulo': 'Reenviar proposta', 'prioridade': 'alta',
        'vencimento': (date.today() + timedelta(days=2)).isoformat(),
        'responsavel_id': str(usuario_operacional.id),
    })
    assert r.status_code == 302
    t = Tarefa.objects.get(titulo='Reenviar proposta')
    assert t.tenant_id == tenant_aurora.id
    assert t.prioridade == 'alta'
    assert t.vencimento == date.today() + timedelta(days=2)
    assert t.responsavel_id == usuario_operacional.id
    assert t.criado_por_id == admin_company.id
    assert not t.concluida


@pytest.mark.django_db
def test_tarefa_sem_titulo_rejeitada(tenant_aurora, admin_company):
    c = _cliente_web(admin_company)
    r = c.post('/tarefas/', {'acao': 'criar', 'titulo': '   '})
    assert r.status_code == 200
    assert 'Informe o título'.encode() in r.content
    assert Tarefa.objects.count() == 0


@pytest.mark.django_db
def test_edita_tarefa(tenant_aurora, admin_company):
    t = _tarefa(tenant_aurora)
    c = _cliente_web(admin_company)
    r = c.post(f'/tarefas/{t.id}/editar/', {
        'titulo': 'Ligar pra confirmar horário',
        'prioridade': 'alta',
        'vencimento': (date.today() + timedelta(days=5)).isoformat(),
    })
    assert r.status_code == 302
    t.refresh_from_db()
    assert t.titulo == 'Ligar pra confirmar horário'
    assert t.prioridade == 'alta'
    assert t.vencimento == date.today() + timedelta(days=5)


# --- Lembretes: seções da lista ---

@pytest.mark.django_db
def test_lista_separa_atrasadas_hoje_proximas(tenant_aurora, admin_company):
    _tarefa(tenant_aurora, titulo='Atrasada X', vencimento=date.today() - timedelta(days=2))
    _tarefa(tenant_aurora, titulo='De hoje Y', vencimento=date.today())
    _tarefa(tenant_aurora, titulo='Futura Z', vencimento=date.today() + timedelta(days=3))
    c = _cliente_web(admin_company)
    html = c.get('/tarefas/').content.decode()
    assert 'Atrasada X' in html
    assert 'De hoje Y' in html
    assert 'Futura Z' in html
    # seções presentes
    assert 'Atrasadas' in html
    assert 'Para hoje' in html
    assert 'Próximas' in html


@pytest.mark.django_db
def test_concluir_e_reabrir(tenant_aurora, admin_company):
    t = _tarefa(tenant_aurora, vencimento=date.today())
    c = _cliente_web(admin_company)
    c.post(f'/tarefas/{t.id}/concluir/', {})
    t.refresh_from_db()
    assert t.concluida
    assert t.concluida_em is not None

    c.post(f'/tarefas/{t.id}/reabrir/', {})
    t.refresh_from_db()
    assert not t.concluida
    assert t.concluida_em is None


# --- Permissões ---

@pytest.mark.django_db
def test_viewer_nao_cria_nem_conclui(tenant_aurora, usuario_viewer):
    c = _cliente_web(usuario_viewer)
    c.post('/tarefas/', {'acao': 'criar', 'titulo': 'X'})
    assert Tarefa.objects.count() == 0

    t = _tarefa(tenant_aurora)
    c.post(f'/tarefas/{t.id}/concluir/', {})
    t.refresh_from_db()
    assert not t.concluida  # viewer não consegue concluir


@pytest.mark.django_db
def test_excluir_somente_admin(tenant_aurora, admin_company, usuario_operacional):
    t = _tarefa(tenant_aurora)
    # operacional tenta excluir → permanece
    c = _cliente_web(usuario_operacional)
    c.post(f'/tarefas/{t.id}/excluir/', {})
    assert Tarefa.objects.filter(pk=t.pk).exists()

    # admin exclui → some
    c2 = _cliente_web(admin_company)
    c2.post(f'/tarefas/{t.id}/excluir/', {})
    assert not Tarefa.objects.filter(pk=t.pk).exists()


# --- Isolamento por tenant ---

@pytest.mark.django_db
def test_tarefas_isoladas_por_tenant(tenant_aurora, tenant_beta, admin_company):
    _tarefa(tenant_aurora, titulo='Só da Aurora')
    c = _cliente_web(admin_company)
    html = c.get('/tarefas/').content.decode()
    assert 'Só da Aurora' in html

    # beta não enxerga a tarefa da aurora
    from acesso.models import Usuario
    from django.contrib.auth.hashers import make_password
    beta_admin = Usuario.objects.create(
        nome='Beta', email='beta@beta.com', role='admin_company', tenant=tenant_beta,
        senha=make_password('senha123'),
    )
    html2 = _cliente_web(beta_admin).get('/tarefas/').content.decode()
    assert 'Só da Aurora' not in html2


# --- Ficha do contato ---

@pytest.mark.django_db
def test_ficha_mostra_tarefas_e_cria_rapido(tenant_aurora, admin_company):
    contato = _contato(tenant_aurora)
    _tarefa(tenant_aurora, titulo='Retornar orçamento', contato=contato)
    c = _cliente_web(admin_company)

    html = c.get(f'/contatos/{contato.id}/').content.decode()
    assert 'Retornar orçamento' in html

    r = c.post(f'/tarefas/contato/{contato.id}/nova/', {
        'titulo': 'Confirmar horário', 'vencimento': date.today().isoformat(),
    })
    assert r.status_code == 302
    t = Tarefa.objects.get(titulo='Confirmar horário')
    assert t.contato_id == contato.id
    assert t.tenant_id == tenant_aurora.id


# --- Correções da revisão ---

@pytest.mark.django_db
def test_criar_tarefa_ignora_contato_de_outro_tenant(tenant_aurora, tenant_beta, admin_company):
    contato_beta = _contato(tenant_beta, nome='Pessoa da Beta')
    c = _cliente_web(admin_company)
    c.post('/tarefas/', {'acao': 'criar', 'titulo': 'X', 'contato_id': str(contato_beta.id)})
    t = Tarefa.objects.get(titulo='X')
    assert t.tenant_id == tenant_aurora.id
    assert t.contato_id is None  # referência de outra clínica descartada


@pytest.mark.django_db
def test_voltar_externo_nao_redireciona(tenant_aurora, admin_company):
    t = _tarefa(tenant_aurora)
    c = _cliente_web(admin_company)
    r = c.post(f'/tarefas/{t.id}/concluir/', {'voltar': 'https://evil.com/'})
    assert r.status_code == 302
    assert 'evil.com' not in r.url


# --- Lembretes no header e no dashboard ---

@pytest.mark.django_db
def test_badge_header_mostra_atrasadas(tenant_aurora, admin_company):
    _tarefa(tenant_aurora, vencimento=date.today() - timedelta(days=1))
    _tarefa(tenant_aurora, vencimento=date.today() - timedelta(days=3))
    c = _cliente_web(admin_company)
    html = c.get('/tarefas/').content.decode()
    assert 'tarefa(s) atrasada(s)' in html  # badge do header com contagem


@pytest.mark.django_db
def test_dashboard_mostra_alerta_de_tarefas(tenant_aurora, admin_company):
    _tarefa(tenant_aurora, titulo='Ligar pra Ana', vencimento=date.today() - timedelta(days=1))
    _tarefa(tenant_aurora, titulo='Hoje: confirmar', vencimento=date.today())
    c = _cliente_web(admin_company)
    html = c.get('/dashboard/').content.decode()
    assert 'Tarefas &amp; lembretes' in html
    assert 'Ligar pra Ana' in html
    assert 'Hoje: confirmar' in html


@pytest.mark.django_db
def test_dashboard_sem_tarefas_nao_mostra_alerta(tenant_aurora, admin_company):
    c = _cliente_web(admin_company)
    html = c.get('/dashboard/').content.decode()
    assert 'Tarefas &amp; lembretes' not in html


@pytest.mark.django_db
def test_admin_saas_nao_quebra(admin_saas):
    c = _cliente_web(admin_saas)
    r = c.get('/tarefas/')
    assert r.status_code == 200
    assert c.get('/dashboard/').status_code == 200
