"""Verifica negócios parados e dispara as automações de estagnação.

Para rodar diariamente (ex.: todo dia útil de manhã), agende no agendador do
servidor (Windows Task Scheduler / cron):

    .venv/Scripts/python manage.py verificar_estagnados

Opcional: `--tenant <id>` restringe a varredura a uma clínica específica.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Dispara as automações de negócios parados (estagnados) há X dias.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=int, default=None, help='Id do tenant (opcional)')

    def handle(self, *args, **options):
        from automacoes.engine import executar_estagnados

        n = executar_estagnados(options['tenant'])
        self.stdout.write(self.style.SUCCESS(f'{n} execução(ões) de estagnação disparada(s)'))
