"""Remove os campos PIX do Tenant — pertenciam ao app 'acordos' (removido)."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('acesso', '0011_tenant_pix'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tenant',
            name='pix_chave',
        ),
        migrations.RemoveField(
            model_name='tenant',
            name='pix_recebedor',
        ),
        migrations.RemoveField(
            model_name='tenant',
            name='pix_cidade',
        ),
    ]
