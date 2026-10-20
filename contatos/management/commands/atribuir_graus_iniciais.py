"""Atribuição inicial de graus aos membros (faixa 4 a 13).

Popula o histórico `graus_membros` de cada membro ATIVO que ainda não tem
nenhum grau registrado, na mesma faixa pedida (4° a 13°). Idempotente: quem já
tem grau no histórico não é tocado; re-executar não duplica (constraint
membro+grau e a checagem de "sem nenhum grau").

Distribuição determinística: a n-ésimo membro elegível recebe o grau
4 + (n % 10), cobrindo 4°..13° em círculo, com a data de hoje (mesmo
comportamento do campo "Grau Atual" do Alterar Membro).
"""
from datetime import date

from django.core.management.base import BaseCommand

from contatos.models import Grau, GrauMembro, Membro

MIN_GRAU = 4
MAX_GRAU = 13


class Command(BaseCommand):
    help = 'Atribui graus entre 4° e 13° aos membros ATIVOS sem grau no histórico.'

    def handle(self, *args, **options):
        hoje = date.today()
        graus = {
            g.numero: g for g in Grau.objects.filter(
                numero__gte=MIN_GRAU, numero__lte=MAX_GRAU,
            )
        }
        faltando = [n for n in range(MIN_GRAU, MAX_GRAU + 1) if n not in graus]
        if faltando:
            nomes = ', '.join(f'{n}°' for n in faltando)
            self.stderr.write(self.style.ERROR(
                'Catálogo incompleto: faltam os graus ' + nomes
                + '. Rode `manage.py seed_graus` antes.'
            ))
            return

        sem_grau = Membro.objects.filter(
            situacao='ATIVO', graus__isnull=True,
        ).order_by('id').distinct()
        atribuidos = 0
        for indice, membro in enumerate(sem_grau):
            numero = MIN_GRAU + (indice % (MAX_GRAU - MIN_GRAU + 1))
            _, created = GrauMembro.objects.get_or_create(
                membro=membro,
                grau=graus[numero],
                defaults={'tenant_id': membro.tenant_id, 'data': hoje},
            )
            if created:
                atribuidos += 1
                self.stdout.write(
                    f'{membro.nome}: {numero}° registrado em {hoje.isoformat()}'
                )
        self.stdout.write(self.style.SUCCESS(
            f'Atribuição concluída: {atribuidos} graus criados; '
            f'{Membro.objects.filter(situacao="ATIVO", graus__isnull=True).distinct().count()} '
            'membros ainda sem grau.'
        ))
