"""Gera o relatório gerencial em PDF e envia por e-mail aos administradores.

Para rodar diariamente (ex.: todo dia útil de manhã), agende no agendador do
servidor (Windows Task Scheduler / cron):

    python manage.py enviar_relatorio

Opcional:
    --tenant <id>      restringe a geração a uma empresa específica.
    --periodo <chave>  hoje | 7 | 30 | mes (padrão: 30).

Sem SMTP configurado (settings.EMAIL_CONFIGURADO = False), o comando roda em
MODO SIMULAÇÃO: gera o PDF e apenas informa o que enviaria, sem disparar nada.
"""

from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from acesso.models import ROLE_ADMIN_COMPANY, Tenant, Usuario
from emails.servico import EMAIL_VAZIO, enviar_mensagem
from relatorios.pdf import gerar_relatorio_pdf
from relatorios.views import _kpis, _periodo_por_chave, _produtividade


class Command(BaseCommand):
    help = 'Gera o relatório gerencial (PDF) e envia por e-mail aos administradores da empresa.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=int, default=None, help='Id do tenant (opcional)')
        parser.add_argument('--periodo', default='30', choices=['hoje', '7', '30', 'mes'],
                            help='Período do relatório (padrão: 30)')

    def handle(self, *args, **options):
        inicio, fim, label, _chave = _periodo_por_chave(options['periodo'], timezone.localdate())

        tenants = Tenant.objects.all()
        if options['tenant'] is not None:
            tenants = tenants.filter(pk=options['tenant'])

        enviados = 0
        for tenant in tenants:
            kpis = _kpis(tenant.pk, inicio, fim)
            produtividade = _produtividade(tenant.pk, inicio, fim)
            pdf = gerar_relatorio_pdf(tenant, label, kpis, produtividade)

            admins = list(Usuario.objects.filter(
                tenant_id=tenant.pk, role=ROLE_ADMIN_COMPANY,
            ).exclude(email__in=EMAIL_VAZIO))
            if not admins:
                self.stdout.write(self.style.WARNING(
                    f'{tenant.nome}: sem admins com e-mail — pulado'))
                continue

            assunto = f'Relatório gerencial · {label} · {tenant.nome}'
            corpo = (
                f'Olá!\n\n'
                f'Segue o relatório gerencial de {label.lower()} da {tenant.nome} '
                f'(gerado em {date.today().strftime("%d/%m/%Y")}).\n\n'
                f'— GPRBRCRM'
            )
            anexo = f'relatorio-gerencial-{date.today():%Y-%m-%d}.pdf'

            # enviar_mensagem centraliza "simulação vs SMTP" (emails/servico.py — PRD 4.1):
            # sem SMTP configurado devolve 'simulado' sem disparar.
            for admin in admins:
                status = enviar_mensagem(
                    assunto, corpo, admin.email,
                    anexo=pdf, anexo_nome=anexo, conteudo_tipo='application/pdf',
                )
                if status == 'simulado':
                    self.stdout.write(self.style.WARNING(
                        f'SIMULAÇÃO — {tenant.nome} → {admin.email}: {assunto} '
                        f'({anexo}, {len(pdf)} bytes)'))
                    enviados += 1
                elif status == 'enviado':
                    self.stdout.write(self.style.SUCCESS(
                        f'{tenant.nome} → {admin.email}: enviado'))
                    enviados += 1
                else:
                    # erro de um admin não derruba o restante (detalhe nos logs do servico)
                    self.stderr.write(f'{tenant.nome} → {admin.email}: ERRO (ver logs)')

        self.stdout.write(self.style.SUCCESS(f'{enviados} e-mail(s) processado(s)'))
