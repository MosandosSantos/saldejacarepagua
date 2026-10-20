from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contatos', '0019_loja_presidente_nome'),
    ]

    operations = [
        migrations.AddField(
            model_name='loja',
            name='secretario_email',
            field=models.CharField(blank=True, default='', max_length=254),
        ),
        migrations.AddField(
            model_name='loja',
            name='tesoureiro_email',
            field=models.CharField(blank=True, default='', max_length=254),
        ),
    ]
