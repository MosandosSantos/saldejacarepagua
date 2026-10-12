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


# ---------------------------------------------------------------------------
# Aviso imediato: evento incluído → toda a loja recebe o e-mail na hora
# ---------------------------------------------------------------------------

@override_settings(TIME_ZONE=TZ_SIGLA)
@pytest.mark.django_db
def test_aviso_imediato_envia_para_a_loja(tenant_aurora, lembrete):
    from agenda import emails
    from contatos.models import Loja

    loja = lembrete['loja']
    todos = emails.destinatarios_do_evento(lembrete['evento'])

    enviados = emails.enviar_aviso_inclusao(
        evento=lembrete['evento'],
        destinatarios=todos,
        tipo='INCLUSAO',
    )
    assert enviados == len(todos)
    assert len(mail.outbox) == 1
    enviado = mail.outbox[0]
    assert enviado.to == todos
    assert 'Sessão Lembretes' in enviado.subject
    assert 'agendado' in enviado.subject.lower() or 'inclusão' in enviado.subject.lower()


@override_settings(TIME_ZONE=TZ_SIGLA)
@pytest.mark.django_db
def test_aviso_imediato_nao_envia_sem_destinatarios(lembrete):
    from agenda import emails
    from contatos.models import Loja, Membro, Filiacao

    # limpa e-mails dos membros da loja: nenhum destinatário
    Filiacao.objects.filter(loja=lembrete['loja']).update()
    from contatos.models import Membro
    Membro.objects.filter(filiacoes__loja=lembrete['loja']).update(email='')

    resultado = emails.enviar_aviso_inclusao(
        evento=lembrete['evento'],
        destinatarios=[],
        tipo='INCLUSAO',
    )
    assert resultado == 0
    assert len(mail.outbox) == 0


@override_settings(TIME_ZONE=TZ_SIGLA)
@pytest.mark.django_db
def test_novo_evento_dispara_aviso_imediato(tenant_aurora, lembrete):
    """Criação via POST /agenda/novo/ dispara o aviso imediato para a loja."""
    from django.test import Client
    from contatos.models import Loja
    from django.contrib.auth.hashers import make_password
    from acesso.models import Usuario

    usuario = Usuario.objects.create(
        nome='S Aviso', email='aviso@agenda.com', role='secretario',
        tenant=tenant_aurora, senha=make_password('senha123'),
    )
    c = Client()
    s = c.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email,
                    'role': usuario.role, 'tenant_id': usuario.tenant_id}
    s.save()
    loja = lembrete['loja']
    tipo = lembrete['evento'].tipo_id
    r = c.post('/agenda/novo/', {
        'loja': str(loja.id), 'tipo': str(tipo),
        'titulo': 'Aviso Imediato', 'data_hora': '2026-12-05T20:00',
        'local': 'Templo', 'descricao': 'prueba',
    })
    assert r.status_code == 302
    assert len(mail.outbox) >= 1
    assunto = mail.outbox[-1].subject
    assert 'Aviso Imediato' in assunto
