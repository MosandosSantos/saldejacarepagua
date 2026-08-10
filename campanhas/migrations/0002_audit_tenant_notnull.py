"""Auditoria DB — Campanha.tenant NOT NULL + backfill.

Antes: `tenant` era `null=True, blank=True` — brecha de isolamento multi-tenant
(registros sem tenant podiam ficar visíveis a admin_saas ou escapar ao filtro).
Agora: obrigatório. Backfill atribui órfãos ao tenant mais antigo.
"""
from django.db import migrations, models


def backfill_tenant_id(apps, schema_editor):
    """Atribui campanhas órfãs (tenant_id IS NULL) ao tenant mais antigo.

    Em ambiente vazio (sem tenants) a operação é no-op.
    """
    Tenant = apps.get_model('acesso', 'Tenant')
    Campanha = apps.get_model('campanhas', 'Campanha')
    primeiro = Tenant.objects.order_by('id').first()
    if primeiro is None:
        return
    Campanha.objects.filter(tenant__isnull=True).update(tenant_id=primeiro.id)


class Migration(migrations.Migration):

    dependencies = [
        ('acesso', '0014_audit_email_lower_index'),
        ('campanhas', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(backfill_tenant_id, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='campanha',
            name='tenant',
            field=models.ForeignKey(
                'acesso.Tenant',
                db_column='tenant_id',
                on_delete=models.CASCADE,
                related_name='campanhas',
            ),
        ),
    ]
