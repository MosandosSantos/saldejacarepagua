import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contatos', '0020_loja_secretario_tesoureiro_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='loja',
            name='secretario',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='lojas_secretariadas',
                to='contatos.membro',
            ),
        ),
        migrations.AddField(
            model_name='loja',
            name='tesoureiro',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='lojas_tesoureiradas',
                to='contatos.membro',
            ),
        ),
    ]
