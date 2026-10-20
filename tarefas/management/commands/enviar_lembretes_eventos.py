"""Management command: envia lembretes de eventos agendados para as proximas 72h.

Roda diariamente as 7h da manha via cron no Docker.
Envia um email para cada membro da loja que tenha evento nas proximas 72h
e que ainda nao tenha recebido o lembrete (lembrete_enviado=False).
"""
import logging
import smtplib
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.utils import timezone

from tarefas.models import Evento
import psycopg

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Envia lembretes de eventos agendados para as proximas 72h'

    def handle(self, *args, **options):
        agora = timezone.now()
        limite = agora + timedelta(hours=72)

        eventos = Evento.objects.filter(
            data_inicio__gte=agora,
            data_inicio__lte=limite,
            lembrete_enviado=False,
        )

        if not eventos.exists():
            self.stdout.write('Nenhum evento para enviar lembrete.')
            return

        total_enviados = 0
        for evento in eventos:
            enviados = self._enviar_lembrete(evento)
            if enviados > 0:
                evento.lembrete_enviado = True
                evento.save(update_fields=['lembrete_enviado'])
                total_enviados += enviados
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Lembrete enviado para {enviados} membros '
                        f'(evento: {evento.titulo} - {evento.data_inicio:%d/%m/%Y %H:%M})'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f'Nenhum membro encontrado para evento: {evento.titulo}'
                    )
                )

        self.stdout.write(self.style.SUCCESS(f'Total de lembretes enviados: {total_enviados}'))

    def _enviar_lembrete(self, evento):
        """Envia lembrete para os membros da loja do evento. Retorna numero de emails enviados."""
        if not getattr(settings, 'EMAIL_CONFIGURADO', False):
            logger.info('Email nao configurado - simulacao de lembrete para evento %s', evento.id)
            return 0

        try:
            from core.gprb.members import emails_membros_da_loja

            membros = emails_membros_da_loja(evento.loja_id)
        except (psycopg.Error, OSError, ValueError):
            logger.exception('Erro ao buscar membros para lembrete (loja %s)', evento.loja_id)
            return 0

        if not membros:
            return 0

        assunto = f'Lembrete: {evento.titulo} em {evento.data_inicio:%d/%m/%Y}'
        corpo = (
            f'Lembrete de sessao agendada para sua loja:\n\n'
            f'Tipo: {evento.get_tipo_display()}\n'
            f'Titulo: {evento.titulo}\n'
            f'Data: {evento.data_inicio:%d/%m/%Y as %H:%M}\n'
            f'Ate: {evento.data_fim:%d/%m/%Y as %H:%M}\n'
        )
        if evento.descricao:
            corpo += f'\nDescricao: {evento.descricao}\n'

        enviados = 0
        for nome, email in membros:
            try:
                msg = EmailMultiAlternatives(
                    subject=assunto,
                    body=corpo,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email],
                )
                msg.send(fail_silently=False)
                enviados += 1
            except (OSError, ValueError, smtplib.SMTPException):
                logger.warning('Falha ao enviar lembrete para %s', email, exc_info=True)

        return enviados
