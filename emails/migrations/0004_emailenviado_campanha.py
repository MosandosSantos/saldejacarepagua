"""Adiciona a FK `campanha` ao EmailEnviado.

S4 do PRD HAZON — Estrutura de campanhas (4.1): os envios disparados por uma
campanha ficam vinculados a ela para exibir KPIs no detalhe.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('campanhas', '0001_initial'),
        ('emails', '0003_emailenviado_cliques_convertido_em'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailenviado',
            name='campanha',
            field=models.ForeignKey(blank=True, help_text='Campanha de origem deste envio (S4 do PRD HAZON)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='envios', to='campanhas.campanha'),
        ),
    ]
