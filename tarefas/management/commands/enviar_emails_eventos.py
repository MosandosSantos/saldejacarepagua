"""Processa a fila durável de e-mails de eventos (envio assíncrono).

Uso manual/operacional: quando o worker em background não correu
(ex.: o servidor reiniciou com e-mails pendentes), este comando reprocessa
as linhas PENDENTE — sem depender de RabbitMQ/Celery: a fila vive no
Postgres e o executor é o que muda.

Ex.: python manage.py enviar_emails_eventos [--limite 200]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from tarefas.models import EmailEventoFila
from tarefas.views import _processar_linha_fila


class Command(BaseCommand):
    help = 'Envia os avisos de evento pendentes da fila (email_evento_fila).'

    def add_arguments(self, parser):
        parser.add_argument('--limite', type=int, default=500)

    def handle(self, *args, **opts):
        limite = max(1, int(opts.get('limite', 500)))
        pendentes = list(
            EmailEventoFila.objects
            .filter(situacao='PENDENTE')
            .order_by('id')[:limite]
        )
        enviados = erros = 0
        for linha in pendentes:
            situacao, erro = _processar_linha_fila(linha)
            linha.situacao = situacao
            linha.tentativas += 1
            linha.erro = erro
            if situacao == 'ENVIADO':
                linha.enviado_em = timezone.now()
                enviados += 1
            else:
                erros += 1
            linha.save(update_fields=['situacao', 'tentativas', 'erro', 'enviado_em'])
        self.stdout.write(f'Processadas {len(pendentes)}: {enviados} enviados, {erros} erros.')
