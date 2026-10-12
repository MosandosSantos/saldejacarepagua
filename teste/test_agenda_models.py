"""Modelos do app agenda — catálogo de tipos, eventos e presenças."""
import datetime

import pytest
from django.db import IntegrityError, transaction


@pytest.fixture
def tenant(db):
    from acesso.models import Tenant

    tenant, _ = Tenant.objects.get_or_create(
        slug='clinica-aurora', defaults={'nome': 'Clínica Aurora'},
    )
    return tenant


@pytest.fixture
def loja(tenant):
    from contatos.models import Loja

    return Loja.objects.create(tenant=tenant, nome='Loja Teste')


@pytest.mark.django_db
def test_tipos_evento_semeados():
    from agenda.models import TipoEvento

    assert TipoEvento.objects.count() >= 7
    assert TipoEvento.objects.filter(nome='Sessão Magna').exists()


@pytest.mark.django_db
def test_evento_fields_round_trip(tenant, loja):
    import datetime

    from agenda.models import EventoAgenda, TipoEvento

    tipo = TipoEvento.objects.get(nome='Sessão Magna')
    evento = EventoAgenda.objects.create(
        tenant=tenant, loja=loja, tipo=tipo, titulo='Sessão 1',
        data_hora=datetime.datetime(2026, 11, 1, 20, 0, tzinfo=datetime.timezone.utc),
        local='Templo',
    )
    salvo = EventoAgenda.objects.get(pk=evento.pk)
    assert salvo.titulo == 'Sessão 1'
    assert salvo.loja_id == loja.id
    assert salvo.tipo_id == tipo.id
    assert salvo.lembrete_48_enviado_em is None
    assert salvo.lembrete_24_enviado_em is None
    assert salvo.google_event_id == ''
    salvo.lembrete_48_enviado_em = datetime.datetime(2026, 10, 30, 7, 0, tzinfo=datetime.timezone.utc)
    salvo.google_event_id = 'gcal-abc'
    salvo.save()
    salvo2 = EventoAgenda.objects.get(pk=evento.pk)
    assert salvo2.google_event_id == 'gcal-abc'
    assert salvo2.lembrete_48_enviado_em is not None


@pytest.mark.django_db
def test_presenca_unica(tenant, loja):
    from contatos.models import Membro
    from agenda.models import EventoAgenda, PresencaEvento, TipoEvento

    tipo = TipoEvento.objects.get(nome='Outro')
    evento = EventoAgenda.objects.create(
        tenant=tenant, loja=loja, tipo=tipo, titulo='Ex',
        data_hora=datetime.datetime(2026, 11, 2, 20, 0, tzinfo=datetime.timezone.utc),
    )
    membro = Membro.objects.create(tenant=tenant, nome='Irmão A')
    PresencaEvento.objects.create(evento=evento, membro=membro, estado='PRESENTE')
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PresencaEvento.objects.create(evento=evento, membro=membro, estado='AUSENTE')
