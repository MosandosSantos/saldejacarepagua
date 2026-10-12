"""Command dos lembretes da agenda (idempotente; loop no serviço compose)."""
import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from agenda.emails import enviar_lembretes
from agenda.models import EventoAgenda


class Command(BaseCommand):
    help = 'Envia lembretes 48h/24h das eventos da agenda quando na janela das 07:00.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--loop', action='store_true',
            help='Roda em loop infinito (serviço cron do compose) — sem isso, executa uma vez e sai.',
        )
        parser.add_argument('--agora', default='',
                            help='Instante para "agora" em testes (ISO 8601; default: agora real).')

    def _tick(self, agora):
        fim = agora + datetime.timedelta(hours=49)
        eventos = EventoAgenda.objects.filter(
            data_hora__gte=agora - datetime.timedelta(hours=1),
            data_hora__lte=fim,
        ).exclude(lembrete_48_enviado_em__isnull=False, lembrete_24_enviado_em__isnull=False)
        enviados = {'48': 0, '24': 0}
        for evento in eventos:
            for estado in ('48', '24'):
                enviados[estado] += enviar_lembretes(evento, estado, agora=agora)
        self.stdout.write(f'agenda_lembretes: 48h={enviados["48"]} 24h={enviados["24"]}')
        return enviados

    def handle(self, *args, **options):
        def _resolver_agora():
            bruto = (options.get('agora') or '').strip()
            if bruto:
                instante = datetime.datetime.fromisoformat(bruto)
                return instante if timezone.is_aware(instante) else timezone.make_aware(instante)
            return timezone.now()

        if options['loop']:
            import time

            tempo = 300
            while True:
                self._tick(_resolver_agora())
                time.sleep(tempo)
        else:
            self._tick(_resolver_agora())
