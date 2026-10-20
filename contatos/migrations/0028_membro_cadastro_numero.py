# 0028 — cadastro maçônico numérico (1 a 9999999, único no sistema).

from django.db import migrations, models


def _preencher_cadastro_numero(apps, schema_editor):
    """Atribui 1..N aos membros existentes pela ordem (nome, id)."""
    Membro = apps.get_model('contatos', 'Membro')
    proximo = 1
    for membro in Membro.objects.all().order_by('nome', 'id'):
        if membro.cadastro_numero is None:
            membro.cadastro_numero = proximo
            membro.save(update_fields=['cadastro_numero'])
            proximo += 1


class Migration(migrations.Migration):

    dependencies = [
        ('contatos', '0027_fix_potencias_simbolismo'),
    ]

    operations = [
        # 1) Coluna sem constraint (para já aceitar backfill).
        migrations.AddField(
            model_name='membro',
            name='cadastro_numero',
            field=models.PositiveIntegerField(blank=True, help_text='Número de cadastro maçônico (1 a 9999999, único no sistema).', null=True),
        ),
        # 2) Backfill determinístico: 1..N pela ordem (nome, id).
        migrations.RunPython(
            _preencher_cadastro_numero,
            migrations.RunPython.noop,
        ),
        # 3) Constraint de unicidade global + índice.
        migrations.AlterField(
            model_name='membro',
            name='cadastro_numero',
            field=models.PositiveIntegerField(blank=True, help_text='Número de cadastro maçônico (1 a 9999999, único no sistema).', null=True, unique=True),
        ),
    ]
