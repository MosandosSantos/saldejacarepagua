"""Semeadura idempotente do catálogo de graus (4 a 33).

O catálogo alimenta o select "Grau atual" do Alterar Membro e o nome exibido
na listagem (`grau_atual.nome`). Nomes ficam genéricos ("Grau N"): o usuário
pode renomear os específicos quando quiser.
"""
from django.core.management.base import BaseCommand

from contatos.models import Grau


class Command(BaseCommand):
    help = 'Semeadura idempotente do catálogo de graus (4 a 33).'

    def handle(self, *args, **options):
        criados = 0
        for numero in range(4, 34):
            grau, created = Grau.objects.get_or_create(
                numero=numero,
                defaults={'nome': f'Grau {numero}'},
            )
            if not grau.nome:
                grau.nome = f'Grau {numero}'
                grau.save(update_fields=['nome'])
            if created:
                criados += 1
        self.stdout.write(self.style.SUCCESS(
            f'Catálogo de graus concluído ({criados} novos, '
            f'{Grau.objects.count()} no total).'
        ))
