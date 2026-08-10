"""Auditoria DB — tenant NOT NULL + índices em contatos.

Mudanças:
1. `tenant` NOT NULL em Carteira, Tag, Contato, Negocio, CampoPersonalizado
   (antes era `null=True, blank=True` — brecha de isolamento multi-tenant).
2. Backfill: órfãos atribuídos ao tenant mais antigo.
3. Índices compostos nos hotspots:
   - Contato: (tenant_id, seg), (tenant_id, lead_score), (tenant_id, tel_normalizado)
   - Negocio: (tenant_id, stage) [CRÍTICA — funil], (tenant_id, updated_at) [estagnados]
"""
from django.db import migrations, models


def backfill_tenant_id(apps, schema_editor):
    """Atribui registros órfãos (tenant_id IS NULL) ao tenant mais antigo.

    Aplica aos 5 modelos do app. Em ambiente vazio (sem tenants) é no-op.
    """
    Tenant = apps.get_model('acesso', 'Tenant')
    primeiro = Tenant.objects.order_by('id').first()
    if primeiro is None:
        return
    for nome in ('Carteira', 'Tag', 'Contato', 'Negocio', 'CampoPersonalizado'):
        Modelo = apps.get_model('contatos', nome)
        Modelo.objects.filter(tenant__isnull=True).update(tenant_id=primeiro.id)


class Migration(migrations.Migration):

    dependencies = [
        ('acesso', '0014_audit_email_lower_index'),
        ('contatos', '0011_carteira_contato_cargo_carteira'),
    ]

    operations = [
        # --- Backfill (antes de remover o NULL) ---
        migrations.RunPython(backfill_tenant_id, migrations.RunPython.noop),

        # --- tenant NOT NULL ---
        migrations.AlterField(
            model_name='carteira',
            name='tenant',
            field=models.ForeignKey(
                'acesso.Tenant',
                db_column='tenant_id',
                on_delete=models.CASCADE,
                related_name='carteiras',
            ),
        ),
        migrations.AlterField(
            model_name='tag',
            name='tenant',
            field=models.ForeignKey(
                'acesso.Tenant',
                db_column='tenant_id',
                on_delete=models.CASCADE,
                related_name='tags',
            ),
        ),
        migrations.AlterField(
            model_name='contato',
            name='tenant',
            field=models.ForeignKey(
                'acesso.Tenant',
                db_column='tenant_id',
                on_delete=models.CASCADE,
                related_name='contatos',
            ),
        ),
        migrations.AlterField(
            model_name='negocio',
            name='tenant',
            field=models.ForeignKey(
                'acesso.Tenant',
                db_column='tenant_id',
                on_delete=models.CASCADE,
                related_name='negocios',
            ),
        ),
        migrations.AlterField(
            model_name='campopersonalizado',
            name='tenant',
            field=models.ForeignKey(
                'acesso.Tenant',
                db_column='tenant_id',
                on_delete=models.CASCADE,
                related_name='campos_personalizados',
            ),
        ),

        # --- Índices: Contato ---
        migrations.AddIndex(
            model_name='contato',
            index=models.Index(fields=['tenant_id', 'seg'], name='cto_tenant_seg_idx'),
        ),
        migrations.AddIndex(
            model_name='contato',
            index=models.Index(fields=['tenant_id', 'lead_score'], name='cto_tenant_score_idx'),
        ),
        migrations.AddIndex(
            model_name='contato',
            index=models.Index(fields=['tenant_id', 'tel_normalizado'], name='cto_tenant_tel_idx'),
        ),

        # --- Índices: Negocio (CRÍTICA — funil de vendas) ---
        migrations.AddIndex(
            model_name='negocio',
            index=models.Index(fields=['tenant_id', 'stage'], name='neg_tenant_stage_idx'),
        ),
        migrations.AddIndex(
            model_name='negocio',
            index=models.Index(fields=['tenant_id', 'updated_at'], name='neg_tenant_upd_idx'),
        ),
    ]
