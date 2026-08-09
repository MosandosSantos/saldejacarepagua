"""Adiciona rastreio de cliques e conversão ao EmailEnviado.

S4 do PRD HAZON — E-mail avançado: rastreio de cliques (4.3.5) e conversão de
propostas (4.3.6).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0002_alter_emailenviado_options_alter_modeloemail_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='emailenviado',
            name='cliques',
            field=models.IntegerField(default=0, help_text='Quantos links do e-mail foram clicados'),
        ),
        migrations.AddField(
            model_name='emailenviado',
            name='ultimo_clique_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='emailenviado',
            name='convertido_em',
            field=models.DateTimeField(blank=True, help_text='Quando um negócio do contato fechou após contato com este e-mail', null=True),
        ),
    ]
