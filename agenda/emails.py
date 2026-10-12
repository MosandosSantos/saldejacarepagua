"""Lembretes da agenda por e-mail — 48h e 24h antes, sempre às 07:00 locais.

O command `agenda_lembretes` chama `enviar_lembretes` a cada tick; a
idempotência vem do timestamp no evento (`lembrete_48/24_enviado_em`).
Janela de disparo: dentro dos 11 minutos seguintes às 07:00 do dia D-2
(48h) ou D-1 (24h) — tolerância do loop de 10 min.
"""
import datetime
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from .models import EventoAgenda
from contatos.models import Filiacao

logger = logging.getLogger(__name__)

JANELA_MINUTOS = 11

DEFINICOES = {
    '48': {'campo': 'lembrete_48_enviado_em', 'horas_antes': 48},
    '24': {'campo': 'lembrete_24_enviado_em', 'horas_antes': 24},
}


def destinatarios_do_evento(evento):
    """E-mails únicos dos membros ATIVOS filiados à loja, com e-mail."""
    ids = (
        Filiacao.objects.filter(loja_id=evento.loja_id)
        .filter(membro__situacao='ATIVO')
        .exclude(membro__email='')
        .values_list('membro__email', flat=True)
    )
    vistos, unicos = set(), []
    for email in ids:
        chave = email.strip().lower()
        if chave and chave not in vistos:
            vistos.add(chave)
            unicos.append(email.strip())
    return unicos


def _horario_disparo(data_hora, horas_antes):
    """07:00 locais do dia (data_hora - horas_antes) no fuso do settings."""
    local = timezone.localtime(data_hora)
    dia = (local - datetime.timedelta(hours=horas_antes)).date()
    return local.replace(year=dia.year, month=dia.month, day=dia.day,
                         hour=7, minute=0, second=0, microsecond=0)


def _na_janela(disparo, agora):
    if not isinstance(agora, datetime.datetime):
        agora = timezone.now()
    if not timezone.is_aware(agora):
        agora = timezone.make_aware(agora, timezone.get_current_timezone())
    disparo_aware = timezone.localtime(disparo)
    return abs((disparo_aware - agora).total_seconds()) <= JANELA_MINUTOS * 60


def _enviar_email(assunto, texto, emails):
    from_address = settings.DEFAULT_FROM_EMAIL
    send_mail(assunto, texto, from_address, emails, html_message=None)


def _assunto(evento):
    loja = getattr(evento, 'loja', None)
    loja_nome = loja.nome if loja else 'Agenda'
    return f'[{loja_nome}] {evento.titulo} — {timezone.localtime(evento.data_hora).strftime("%d/%m/%Y %H:%M")}'


def _corpo(evento):
    loja_nome = getattr(getattr(evento, 'loja', None), 'nome', '—')
    tipo_nome = getattr(getattr(evento, 'tipo', None), 'nome', '—')
    local = evento.local or 'A informar'
    return (
        f'{evento.titulo}\n'
        f'Tipo: {tipo_nome}\n'
        f'Loja: {loja_nome}\n'
        f'Data: {timezone.localtime(evento.data_hora).strftime("%d/%m/%Y %H:%M")}\n'
        f'Local: {local}\n'
        '\nAgenda completa: /agenda/\n'
    )


ASSUNTOS_AVISO = {
    'INCLUSAO': 'agendado',
}


def enviar_aviso_inclusao(evento, destinatarios=None, tipo='INCLUSAO'):
    """Aviso imediato ao incluir um evento: a loja inteira recebe agora.

    Retorna a quantidade de envios (0 se nada configurado/nenhum destino).
    """
    if not getattr(settings, 'EMAIL_CONFIGURADO', False):
        return 0
    if destinatarios is None:
        destinatarios = destinatarios_do_evento(evento)
    if not destinatarios:
        return 0
    rotulo = ASSUNTOS_AVISO.get(tipo, tipo.lower())
    quando = timezone.localtime(evento.data_hora).strftime('%d/%m/%Y %H:%M')
    assunto = (
        f'[{evento.loja.nome}] {evento.titulo} — {rotulo} para {quando}'
    )
    _enviar_email(assunto, _corpo(evento), destinatarios)
    logger.info('Aviso imediato do evento %s enviado a %d membros', evento.id, len(destinatarios))
    return len(destinatarios)


def enviar_lembretes(evento, estado, agora=None):
    """Envia um lembrete ('48' ou '24') se estiver na janela e ainda não enviado.

    Retorna a quantidade de envios (1 ou 0 — o e-mail é único para todos).
    Falha SMTP levanta: o timestamp NÃO é marcado — o próximo tick retenta.
    """
    definicao = DEFINICOES[estado]
    campo = definicao['campo']
    if getattr(evento, campo) is not None:
        return 0
    if not getattr(settings, 'EMAIL_CONFIGURADO', False):
        return 0
    disparo = _horario_disparo(evento.data_hora, definicao['horas_antes'])
    if not _na_janela(disparo, agora):
        return 0

    destinatarios = destinatarios_do_evento(evento)
    if not destinatarios:
        # Ninguém com e-mail: marca para não reprocessar a janela em vão.
        setattr(evento, campo, timezone.now())
        evento.save(update_fields=[campo])
        return 0
    logger.info(
        'Lembrete %s do evento %s (membros sem e-mail são pulados)', estado, evento.id)
    _enviar_email(_assunto(evento), _corpo(evento), destinatarios)
    setattr(evento, campo, timezone.now())
    evento.save(update_fields=[campo])
    return len(destinatarios)
