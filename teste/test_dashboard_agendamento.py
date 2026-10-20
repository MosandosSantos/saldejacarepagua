"""Quadro Agendamento do dashboard — sessões realizadas × agendadas por loja.

Fontes: agenda.EventoAgenda (lembretes) e tarefas.Evento (Agenda de Sessões,
onde os eventos são criados no CRM). Regressão do quadro vazio: os eventos
criados na Agenda de Sessões agora entram na contagem.
"""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.utils import timezone

from acesso.models import Tenant
from contatos.models import Loja
from dashboard.repositories.local_repository import LocalRepository

pytestmark = pytest.mark.django_db(transaction=True)


def _mundo():
    sufixo = uuid4().hex
    tenant = Tenant.objects.create(nome='Vale Agend', slug=f'agend-{sufixo}')
    loja_a = Loja.objects.create(tenant=tenant, nome='Loja Agend A')
    loja_b = Loja.objects.create(tenant=tenant, nome='Loja Agend B')
    return SimpleNamespace(
        tenant=tenant, loja_a=loja_a, loja_b=loja_b, sufixo=sufixo,
    )


def test_eventos_da_agenda_de_sessoes_aparecem_no_quadro():
    from tarefas.models import Evento

    mundo = _mundo()
    agora = timezone.now()
    Evento.objects.create(
        titulo='Passada', data_inicio=agora - timedelta(days=10),
        data_fim=agora - timedelta(days=10) + timedelta(hours=2),
        loja_id=str(mundo.loja_a.pk),
    )
    Evento.objects.create(
        titulo='Futura 1', data_inicio=agora + timedelta(days=5),
        data_fim=agora + timedelta(days=5) + timedelta(hours=2),
        loja_id=str(mundo.loja_a.pk),
    )
    Evento.objects.create(
        titulo='Futura 2', data_inicio=agora + timedelta(days=9),
        data_fim=agora + timedelta(days=9) + timedelta(hours=2),
        loja_id=str(mundo.loja_b.pk),
    )

    dados = {r['loja']: r for r in LocalRepository(mundo.tenant.pk).agendamento_lojas()}

    assert dados['Loja Agend A']['realizadas'] == 1
    assert dados['Loja Agend A']['agendadas'] == 1
    assert dados['Loja Agend B']['realizadas'] == 0
    assert dados['Loja Agend B']['agendadas'] == 1


def test_loja_de_outro_tenant_nao_vaz_no_quadro_restrito():
    """Com tenant_id da sessão, eventos de loja de outro tenant ficam de fora."""
    from tarefas.models import Evento

    mundo = _mundo()
    tenant_b = Tenant.objects.create(
        nome='Vale Agend B', slug=f'agendb-{uuid4().hex}',
    )
    loja_fora = Loja.objects.create(tenant=tenant_b, nome='Loja Fora')
    agora = timezone.now()
    Evento.objects.create(
        titulo='Fora do escopo', data_inicio=agora + timedelta(days=3),
        data_fim=agora + timedelta(days=3) + timedelta(hours=2),
        loja_id=str(loja_fora.pk),
    )
    Evento.objects.create(
        titulo='No escopo', data_inicio=agora + timedelta(days=3),
        data_fim=agora + timedelta(days=3) + timedelta(hours=2),
        loja_id=str(mundo.loja_a.pk),
    )

    dados = {r['loja']: r for r in LocalRepository(mundo.tenant.pk).agendamento_lojas()}

    assert 'Loja Fora' not in dados
    assert dados['Loja Agend A']['agendadas'] == 1


def test_codigo_legado_uuid_agrupa_como_loja_externa():
    from tarefas.models import Evento

    mundo = _mundo()
    codigo = f'{uuid4()}'  # formato legado (UUID do banco externo)
    agora = timezone.now()
    Evento.objects.create(
        titulo='Legado', data_inicio=agora - timedelta(days=2),
        data_fim=agora - timedelta(days=2) + timedelta(hours=2),
        loja_id=codigo,
    )

    dados = {r['loja']: r for r in LocalRepository(mundo.tenant.pk).agendamento_lojas()}

    rotulo = f'Loja externa ({codigo[:8]}…)'
    assert rotulo in dados
    assert dados[rotulo]['realizadas'] == 1


def test_admin_saas_sem_tenant_ve_lojas_de_todos_os_vales():
    from tarefas.models import Evento

    mundo = _mundo()
    tenant_b = Tenant.objects.create(
        nome='Vale Agend C', slug=f'agendc-{uuid4().hex}',
    )
    loja_b2 = Loja.objects.create(tenant=tenant_b, nome='Loja Agend C1')
    agora = timezone.now()
    Evento.objects.create(
        titulo='A qualquer', data_inicio=agora + timedelta(days=1),
        data_fim=agora + timedelta(days=1) + timedelta(hours=2),
        loja_id=str(mundo.loja_a.pk),
    )
    Evento.objects.create(
        titulo='B qualquer', data_inicio=agora + timedelta(days=1),
        data_fim=agora + timedelta(days=1) + timedelta(hours=2),
        loja_id=str(loja_b2.pk),
    )

    dados = {r['loja'] for r in LocalRepository(None).agendamento_lojas()}

    assert 'Loja Agend A' in dados
    assert 'Loja Agend C1' in dados
