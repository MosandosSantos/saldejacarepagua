"""Número de cadastro próprio da conta de login."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('acesso', '0023_usuario_membro'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='cadastro_numero',
            field=models.PositiveIntegerField(
                blank=True,
                help_text=('Número de cadastro próprio da conta, usado no login '
                           '(para contas administrativas sem membro vinculado)'),
                null=True,
                unique=True,
            ),
        ),
    ]
