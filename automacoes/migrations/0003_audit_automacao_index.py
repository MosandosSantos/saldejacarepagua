"""Auditoria DB — índice composto em automacoes.

Padrão de query do engine (automacoes/engine.py:disparar, roda em cada
evento de contato/negócio):
    filter(tenant_id=?, ativa=True, trigger=evento)
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('automacoes', '0002_alter_automacao_options_and_more'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='automacao',
            index=models.Index(
                fields=['tenant_id', 'trigger', 'ativa'],
                name='aut_tenant_trigger_idx',
            ),
        ),
    ]
