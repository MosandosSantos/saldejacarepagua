from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contatos', '0018_loja_pdf_required'),
    ]

    operations = [
        migrations.AddField(
            model_name='loja',
            name='presidente_nome',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
    ]
