"""Modelo Tarefa — follow-ups e lembretes do time, escopados por tenant.

Cada tarefa tem título, descrição, contato (opcional), responsável (opcional),
prioridade, vencimento e status. O vencimento alimenta os lembretes: atrasadas,
de hoje, próximas — com badge no header e alerta no dashboard.
"""

from django.db import models
from django.db.models import Count, Q
from django.utils import timezone

PRIORIDADES = [
    ('baixa', 'Baixa'),
    ('media', 'Média'),
    ('alta', 'Alta'),
]

PRIORIDADE_CORES = {
    'baixa': '#94a3b8',
    'media': '#74b3c6',
    'alta': '#fbbf24',
}


class Tarefa(models.Model):
    """Tarefa/follow-up do time (ex.: 'Ligar pra retornar o orçamento')."""

    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='tarefas',
    )
    titulo = models.TextField()
    descricao = models.TextField(blank=True, default='')
    contato = models.ForeignKey(
        'contatos.Contato',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tarefas',
    )
    responsavel = models.ForeignKey(
        'acesso.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tarefas',
    )
    prioridade = models.TextField(choices=PRIORIDADES, default='media')
    vencimento = models.DateField(null=True, blank=True)
    hora = models.TimeField(null=True, blank=True)
    concluida = models.BooleanField(default=False)
    concluida_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(
        'acesso.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tarefas_criadas',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tarefas'
        ordering = ['concluida', 'vencimento', 'hora', 'id']
        indexes = [
            models.Index(fields=['tenant_id', 'concluida', 'vencimento'], name='tar_tenant_status_due_idx'),
        ]

    def __str__(self):
        return f'{self.titulo} ({self.tenant_id})'

    @property
    def atrasada(self):
        return bool(self.vencimento and not self.concluida and self.vencimento < timezone.localdate())


def resumo_tarefas(tenant_id):
    """Contagens para o badge do header (admin_saas = zero). Uma única query agregada."""
    if tenant_id is None:
        return {'atrasadas': 0, 'hoje': 0, 'abertas': 0}
    hoje = timezone.localdate()
    agg = (
        Tarefa.objects.filter(tenant_id=tenant_id, concluida=False)
        .aggregate(
            atrasadas=Count('id', filter=Q(vencimento__lt=hoje)),
            hoje=Count('id', filter=Q(vencimento=hoje)),
            abertas=Count('id'),
        )
    )
    return {'atrasadas': agg['atrasadas'], 'hoje': agg['hoje'], 'abertas': agg['abertas']}


def concluir_tarefa(tarefa):
    """Marca como concluída (idempotente)."""
    if not tarefa.concluida:
        tarefa.concluida = True
        tarefa.concluida_em = timezone.now()
        tarefa.save(update_fields=['concluida', 'concluida_em'])


def reabrir_tarefa(tarefa):
    """Reabre uma tarefa concluída."""
    if tarefa.concluida:
        tarefa.concluida = False
        tarefa.concluida_em = None
        tarefa.save(update_fields=['concluida', 'concluida_em'])
