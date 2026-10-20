from django.core.management.base import BaseCommand

from contatos.models import GrauMembro


class Command(BaseCommand):
    help = 'Remove o histórico sintético de graus após confirmação explícita.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirma a exclusão de todos os registros GrauMembro.',
        )

    def handle(self, *args, **options):
        total = GrauMembro.objects.count()
        if not options['confirm']:
            self.stdout.write(
                f'{total} registros de histórico seriam removidos; nenhum foi apagado. '
                'Use --confirm para confirmar a limpeza do banco de teste.'
            )
            return

        removidos, _ = GrauMembro.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(
            f'Limpeza confirmada: {removidos} registros de histórico removidos.'
        ))
