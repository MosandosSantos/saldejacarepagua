"""Auto-sync Google Calendar para eventos do ranking (tarefas.Evento).

Diferente do app `agenda` (sync por botão, calendário por tenant), os
eventos do ranking são por loja GPRB (loja_id, sem Tenant FK) e grava
automaticamente no calendário apontado por GOOGLE_RANKING_CALENDAR_ID.
"""
import json
from uuid import uuid4

import pytest
from django.test import Client

CALENDAR_ID = 'cal-ranking@group.calendar.google.com'

SENHA = 'senha123'


def _cliente_web(usuario):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {
        'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
        'tenant_id': usuario.tenant_id, 'loja_id': 'loja-gprb-uuid-1',
    }
    s.save()
    return c


def _criar_usuario(nome, email, role, tenant):
    from django.contrib.auth.hashers import make_password

    from acesso.models import Usuario

    return Usuario.objects.create(
        nome=nome, email=email, role=role, tenant=tenant, senha=make_password(SENHA),
    )


@pytest.fixture
def usuario_sec(tenant_aurora):
    return _criar_usuario('Sec Ranking', f'sr-{uuid4().hex[:6]}@g.cal', 'secretario', tenant_aurora)


@pytest.fixture
def calendario_env(monkeypatch):
    monkeypatch.setenv('GOOGLE_RANKING_CALENDAR_ID', CALENDAR_ID)


@pytest.fixture
def cliente_falso(monkeypatch):
    """Substitui o client do Google por um fake que grava as chamadas."""
    from tarefas import google_sync

    chamadas = {'insert': [], 'update': [], 'delete': []}

    def _fake_cliente(calendar_id):
        class _C:
            def insert(self, calendarId, body):
                chamadas['insert'].append((calendarId, body))
                return self

            def update(self, eventId=None, calendarId=None, body=None):
                chamadas['update'].append((eventId, calendarId, body))
                return self

            def delete(self, eventId=None, calendarId=None):
                chamadas['delete'].append((eventId, calendarId))
                return self

            def execute(self):
                return {'id': 'gcal-ranking-1'}

        return _C()

    monkeypatch.setattr(google_sync, '_cliente_do_calendar', _fake_cliente)
    return chamadas


def _dados_json(titulo='Sessão de Teste'):
    return json.dumps({
        'titulo': titulo,
        'descricao': 'desc',
        'tipo': 'sessao',
        'data_inicio': '2026-11-05T20:00',
        'data_fim': '2026-11-05T22:00',
    })


@pytest.mark.django_db
def test_criar_grava_no_google(usuario_sec, calendario_env, cliente_falso):
    r = _cliente_web(usuario_sec).post(
        '/tarefas/eventos/criar/', _dados_json(), content_type='application/json')
    assert r.status_code == 200, r.content
    assert len(cliente_falso['insert']) == 1
    calendar_id, corpo = cliente_falso['insert'][0]
    assert calendar_id == CALENDAR_ID
    assert corpo['summary'] == '[Sessão] Sessão de Teste'  # tipo como prefixo legível no calendário
    assert corpo['start']['dateTime'].startswith('2026-11-05T20:00')
    assert corpo['end']['dateTime'].startswith('2026-11-05T22:00')
    from tarefas.models import Evento
    ev = Evento.objects.get(titulo='Sessão de Teste')
    assert ev.google_event_id == 'gcal-ranking-1'


@pytest.mark.django_db
def test_sem_calendar_id_salva_normal(usuario_sec, monkeypatch):
    """Sem GOOGLE_RANKING_CALENDAR_ID, evento salva e nenhum sync é chamado."""
    monkeypatch.delenv('GOOGLE_RANKING_CALENDAR_ID', raising=False)
    from tarefas import google_sync

    chamadas = []

    def _falha(*a, **kw):
        chamadas.append(a)
        raise AssertionError('não deveria construir client sem calendar_id')

    monkeypatch.setattr(google_sync, '_cliente_do_calendar', _falha)
    r = _cliente_web(usuario_sec).post(
        '/tarefas/eventos/criar/', _dados_json(), content_type='application/json')
    assert r.status_code == 200
    assert not chamadas
    from tarefas.models import Evento
    assert Evento.objects.filter(titulo='Sessão de Teste').exists()


@pytest.mark.django_db
def test_google_fora_do_ar_nao_trava_o_salvamento(usuario_sec, calendario_env, monkeypatch):
    """Google indisponível: evento salva no CRM, sync é best-effort."""
    from tarefas import google_sync

    def _falha(calendar_id):
        raise RuntimeError('Google fora do ar')

    monkeypatch.setattr(google_sync, '_cliente_do_calendar', _falha)
    r = _cliente_web(usuario_sec).post(
        '/tarefas/eventos/criar/', _dados_json(), content_type='application/json')
    assert r.status_code == 200
    from tarefas.models import Evento
    assert Evento.objects.filter(titulo='Sessão de Teste').exists()


@pytest.mark.django_db
def test_editar_atualiza_no_google(usuario_sec, calendario_env, cliente_falso):
    client = _cliente_web(usuario_sec)
    client.post('/tarefas/eventos/criar/', _dados_json(), content_type='application/json')
    from tarefas.models import Evento
    ev = Evento.objects.get(titulo='Sessão de Teste')

    r = client.post(
        f'/tarefas/eventos/{ev.id}/editar/',
        json.dumps({'titulo': 'Sessão Editada',
                    'data_inicio': '2026-11-06T19:00',
                    'data_fim': '2026-11-06T21:00'}),
        content_type='application/json')
    assert r.status_code == 200, r.content
    assert len(cliente_falso['update']) == 1
    event_id, calendar_id, corpo = cliente_falso['update'][0]
    assert event_id == 'gcal-ranking-1'
    assert calendar_id == CALENDAR_ID
    assert corpo['summary'] == '[Sessão] Sessão Editada'


@pytest.mark.django_db
def test_excluir_remove_no_google(usuario_sec, calendario_env, cliente_falso):
    client = _cliente_web(usuario_sec)
    client.post('/tarefas/eventos/criar/', _dados_json(), content_type='application/json')
    from tarefas.models import Evento
    ev = Evento.objects.get(titulo='Sessão de Teste')

    r = client.post(f'/tarefas/eventos/{ev.id}/excluir/')
    assert r.status_code == 200
    assert cliente_falso['delete'] == [('gcal-ranking-1', CALENDAR_ID)]
    from tarefas.models import Evento
    assert not Evento.objects.filter(id=ev.id).exists()
