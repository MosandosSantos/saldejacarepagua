"""Lembretes por e-mail: 48h/24h às 07:00, idempotentes, falha SMTP não marca."""
import datetime
from zoneinfo import ZoneInfo

import pytest
from django.core import mail
from django.test import override_settings

TZ_SIGLA = 'America/Sao_Paulo'


def _tz():
    from zoneinfo import ZoneInfo

    return ZoneInfo(TZ_SIGLA)


@pytest.fixture
def lembrete(db, tenant_aurora):
    """Evento com data D-2 07:00 no fuso, a partir de 2026-10-14 00:00 UTC."""
    from agenda.models import EventoAgenda, TipoEvento
    from contatos.models import Filiacao, Loja, Membro

    loja = Loja.objects.create(tenant=tenant_aurora, nome='Loja Emails')
    tipo = TipoEvento.objects.get(nome='Sessão Magna')
    base = datetime.datetime(2026, 10, 14, 10, 0, 0, tzinfo=ZoneInfo('UTC'))
    evento = EventoAgenda.objects.create(
        tenant=tenant_aurora, loja=loja, tipo=tipo, titulo='Sessão Lembretes',
        data_hora=base,
    )
    membros = []
    for i, nome in enumerate(['M A', 'M B', 'M C']):
        m = Membro.objects.create(
            tenant=tenant_aurora, nome=nome, situacao='ATIVO',
            email=f'm{i}@loja.com',
        )
        Filiacao.objects.create(tenant=tenant_aurora, membro=m, loja=loja)
        membros.append(m)
    sem_email = Membro.objects.create(
        tenant=tenant_aurora, nome='M Sem', situacao='ATIVO', email='')
    Filiacao.objects.create(tenant=tenant_aurora, membro=sem_email, loja=loja)
    return {
        'evento': evento, 'membros': membros, 'loja': loja,
    }


# 2026-10-14 10:00 UTC = 07:00 America/Sao_Paulo (UTC-3).
# Evento 2026-10-14 10:00 UTC: 48h antes = 2026-10-12 10:00 UTC = 12/10 às 07:00 loc.
AGORA_NA_JANELA = datetime.datetime(2026, 10, 12, 10, 2, 0, tzinfo=ZoneInfo('UTC'))
AGORA_FORA_JANELA = datetime.datetime(2026, 10, 12, 18, 0, 0, tzinfo=ZoneInfo('UTC'))


@override_settings(TIME_ZONE=TZ_SIGLA, SEND_EMAILS=False)
@pytest.mark.django_db
def test_envia_48h_e_marca_timestamp(lembrete):
    from agenda import emails

    monkeypatched = False
    assert emails.enviar_lembretes(
        lembrete['evento'], '48', agora=AGORA_NA_JANELA) == 3
    lembrete['evento'].refresh_from_db()
    assert lembrete['evento'].lembrete_48_enviado_em is not None
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ['m0@loja.com', 'm1@loja.com', 'm2@loja.com']


@override_settings(TIME_ZONE=TZ_SIGLA)
@pytest.mark.django_db
def test_reexecucao_nao_duplica(lembrete):
    from agenda import emails

    primeira = emails.enviar_lembretes(lembrete['evento'], '48', agora=AGORA_NA_JANELA)
    segunda = emails.enviar_lembretes(lembrete['evento'], '48', agora=AGORA_NA_JANELA)
    assert (primeira, segunda) == (3, 0)
    assert len(mail.outbox) == 1


@override_settings(TIME_ZONE=TZ_SIGLA)
@pytest.mark.django_db
def test_fora_da_janela_nao_envia(lembrete):
    from agenda import emails

    assert emails.enviar_lembretes(
        lembrete['evento'], '48', agora=AGORA_FORA_JANELA) == 0
    lembrete['evento'].refresh_from_db()
    assert lembrete['evento'].lembrete_48_enviado_em is None


@pytest.mark.django_db
def test_membro_sem_email_nao_quebra(lembrete):
    from agenda import emails
    from contatos.models import Membro, Filiacao

    assert emails.destinatarios_do_evento(lembrete['evento']) == [
        'm0@loja.com', 'm1@loja.com', 'm2@loja.com',
    ]


@override_settings(TIME_ZONE=TZ_SIGLA)
@pytest.mark.django_db
def test_smtp_falho_nao_marca_timestamp(lembrete, monkeypatch):
    from agenda import emails

    def _falha(*args, **kwargs):
        raise ConnectionError('smtp morto')

    monkeypatch.setattr(emails, '_enviar_email', _falha)
    with pytest.raises(ConnectionError):
        emails.enviar_lembretes(lembrete['evento'], '48', agora=AGORA_NA_JANELA)
    lembrete['evento'].refresh_from_db()
    assert lembrete['evento'].lembrete_48_enviado_em is None


@override_settings(TIME_ZONE=TZ_SIGLA)
@pytest.mark.django_db
def test_command_lembretes(lembrete, monkeypatch, capsys):
    from django.core.management import call_command

    call_command('agenda_lembretes', agora=AGORA_NA_JANELA.isoformat())
    saida = capsys.readouterr().out
    assert '48h=3' in saida and '24h=0' in saida  # 3 destinatários com e-mail
