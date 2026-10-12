"""Sincronização de eventos com o Google Calendar (Service Account)."""
import datetime
from uuid import uuid4

import pytest
from django.test import Client, RequestFactory


def _cliente_web(usuario):
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s.save()
    return c


def _criar_usuario(nome, email, role, tenant):
    from django.contrib.auth.hashers import make_password
    from acesso.models import Usuario

    return Usuario.objects.create(
        nome=nome, email=email, role=role, tenant=tenant, senha=make_password('senha123'),
    )


@pytest.fixture
def evento_gcal(db, tenant_aurora):
    from agenda.models import EventoAgenda, TipoEvento
    from contatos.models import Loja

    loja = Loja.objects.create(tenant=tenant_aurora, nome='Loja G')
    tipo = TipoEvento.objects.get(nome='Outro')
    return EventoAgenda.objects.create(
        tenant=tenant_aurora, loja=loja, tipo=tipo, titulo='G Evento',
        data_hora=datetime.datetime(2026, 11, 10, 20, 0, tzinfo=datetime.timezone.utc),
    )


@pytest.fixture
def usuario_sec(tenant_aurora):
    return _criar_usuario('S', f's-{uuid4().hex[:6]}@g.cal', 'secretario', tenant_aurora)


@pytest.mark.django_db
def test_tenant_tem_campo_google_calendar_id(tenant_aurora):
    tenant_aurora.google_calendar_id = 'cal-123@group.calendar.google.com'
    tenant_aurora.save()
    tenant_aurora.refresh_from_db()
    assert tenant_aurora.google_calendar_id == 'cal-123@group.calendar.google.com'


@pytest.mark.django_db
def test_sem_calendar_id_retorna_none(evento_gcal):
    from agenda import google_sync

    assert google_sync.sincronizar_google(evento_gcal) is None
    assert evento_gcal.google_event_id == ''


@pytest.mark.django_db
def test_com_calendar_id_grava_google_event_id(evento_gcal, tenant_aurora, monkeypatch):
    from agenda import google_sync

    tenant_aurora.google_calendar_id = 'cal-abc@group.calendar.google.com'
    tenant_aurora.save()

    def _fake_cliente(calendar_id):
        class _C:
            def insert(self, calendarId, body):
                self.corpo = body
                return self

            def execute(self):
                return {'id': 'gcal-xyz'}

        return _C()

    monkeypatch.setattr(google_sync, '_cliente_do_calendar', _fake_cliente)

    assert google_sync.sincronizar_google(evento_gcal) == 'gcal-xyz'
    evento_gcal.refresh_from_db()
    assert evento_gcal.google_event_id == 'gcal-xyz'


@pytest.mark.django_db
def test_remover_google_engole_excecao(evento_gcal, tenant_aurora, monkeypatch):
    from agenda import google_sync

    tenant_aurora.google_calendar_id = 'cal-abc@group.calendar.google.com'
    tenant_aurora.save()
    evento_gcal.google_event_id = 'gcal-404'
    evento_gcal.save()

    def _fake_cliente(calendar_id):
        class _C:
            def delete(self, eventId=None, calendarId=None):
                raise RuntimeError('boom')

            def execute(self):
                return {}

        return _C()

    monkeypatch.setattr(google_sync, '_cliente_do_calendar', _fake_cliente)
    assert google_sync.remover_google(evento_gcal) is False


@pytest.mark.django_db
def test_view_google_sync(evento_gcal, tenant_aurora, usuario_sec, monkeypatch):
    from agenda import google_sync

    tenant_aurora.google_calendar_id = 'cal-view@group.calendar.google.com'
    tenant_aurora.save()

    def _fake_cliente(calendar_id):
        class _C:
            def insert(self, calendarId, body):
                return self

            def execute(self):
                return {'id': 'gcal-view-1'}

        return _C()

    monkeypatch.setattr(google_sync, '_cliente_do_calendar', _fake_cliente)
    r = _cliente_web(usuario_sec).post(f'/agenda/{evento_gcal.id}/google/')
    assert r.status_code == 302
    evento_gcal.refresh_from_db()
    assert evento_gcal.google_event_id == 'gcal-view-1'


@pytest.mark.django_db
def test_viewer_nao_sincroniza(evento_gcal, tenant_aurora, monkeypatch):
    usuario = _criar_usuario('V', f'v-{uuid4().hex[:6]}@g.cal', 'viewer', tenant_aurora)
    r = _cliente_web(usuario).post(f'/agenda/{evento_gcal.id}/google/')
    assert r.status_code == 403
    evento_gcal.refresh_from_db()
    assert evento_gcal.google_event_id == ''
