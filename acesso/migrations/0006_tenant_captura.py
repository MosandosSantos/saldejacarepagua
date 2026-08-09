import secrets

from django.db import migrations, models


def backfill_tokens(apps, schema_editor):
    """Gera token de captura para os tenants existentes (sem token)."""
    Tenant = apps.get_model('acesso', 'Tenant')
    for t in Tenant.objects.all().iterator():
        if not t.token_captura:
            t.token_captura = secrets.token_urlsafe(18)
            t.save(update_fields=['token_captura'])


class Migration(migrations.Migration):

    dependencies = [
        ('acesso', '0005_tenant_dono'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='token_captura',
            field=models.CharField(blank=True, help_text='Token público do formulário de captura de lead (gerado sob demanda)', max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='tenant',
            name='origem_captura',
            field=models.TextField(default='Site', help_text='Origem gravada nos contatos vindos do formulário (ex.: Site, Instagram, WhatsApp)'),
        ),
        migrations.AddField(
            model_name='tenant',
            name='captura_ativa',
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(backfill_tokens, migrations.RunPython.noop),
    ]
