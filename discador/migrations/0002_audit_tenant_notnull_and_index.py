"""Auditoria DB — tenant NOT NULL em Script/Fila/Chamada + índice em Chamada.

Antes: `tenant` era `null=True, blank=True` — brecha de isolamento multi-tenant.
Agora: obrigatório. Backfill atribui órfãos ao tenant mais antigo.

Inclui índice composto (tenant_id, status) em chamadas — usado em filtros de
histórico e relatórios do discador.
"""
from django.db import migrations, models


def backfill_tenant_id(apps, schema_editor):
    """Atribui registros órfãos (tenant_id IS NULL) ao tenant mais antigo.

    Aplica a Script, Fila e Chamada. Em ambiente vazio (sem tenants) é no-op.
    """
    Tenant = apps.get_model('acesso', 'Tenant')
    primeiro = Tenant.objects.order_by('id').first()
    if primeiro is None:
        return
    for nome in ('Script', 'Fila', 'Chamada'):
        Modelo = apps.get_model('discador', nome)
        Modelo.objects.filter(tenant__isnull=True).update(tenant_id=primeiro.id)


class Migration(migrations.Migration):

    dependencies = [
        ('acesso', '0014_audit_email_lower_index'),
        ('discador', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(backfill_tenant_id, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='script',
            name='tenant',
            field=models.ForeignKey(
                'acesso.Tenant',
                db_column='tenant_id',
                on_delete=models.CASCADE,
                related_name='scripts',
            ),
        ),
        migrations.AlterField(
            model_name='fila',
            name='tenant',
            field=models.ForeignKey(
                'acesso.Tenant',
                db_column='tenant_id',
                on_delete=models.CASCADE,
                related_name='filas',
            ),
        ),
        migrations.AlterField(
            model_name='chamada',
            name='tenant',
            field=models.ForeignKey(
                'acesso.Tenant',
                db_column='tenant_id',
                on_delete=models.CASCADE,
                related_name='chamadas',
            ),
        ),
        migrations.AddIndex(
            model_name='chamada',
            index=models.Index(
                fields=['tenant_id', 'status'],
                name='cha_tenant_status_idx',
            ),
        ),
    ]
