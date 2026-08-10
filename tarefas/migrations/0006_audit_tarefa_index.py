"""Auditoria DB — índice composto em tarefas.

Padrão de query do badge (tarefas/models.py:resumo_tarefas, roda em toda
requisição autenticada):
    filter(tenant_id=?, concluida=False) + filter(vencimento__lt/gt=hoje)

Sem índice composto (tenant_id, concluida, vencimento) cada render do badge
faz full scan da tabela de tarefas do tenant.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tarefas', '0005_alter_tarefa_options'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='tarefa',
            index=models.Index(
                fields=['tenant_id', 'concluida', 'vencimento'],
                name='tar_tenant_status_due_idx',
            ),
        ),
    ]
