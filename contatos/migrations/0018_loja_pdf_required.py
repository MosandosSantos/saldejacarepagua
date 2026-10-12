import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contatos', '0017_loja_membro_locais'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lojapdf',
            name='loja',
            field=models.OneToOneField(
                db_column='loja_id',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='pdf',
                to='contatos.Loja',
            ),
        ),
    ]
