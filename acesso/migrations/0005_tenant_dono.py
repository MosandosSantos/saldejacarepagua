import django.db.models.deletion
from django.db import migrations, models


def backfill_dono(apps, schema_editor):
    """Define o dono inicial de cada tenant: o primeiro admin_company criado."""
    Tenant = apps.get_model('acesso', 'Tenant')
    Usuario = apps.get_model('acesso', 'Usuario')
    for tenant in Tenant.objects.all():
        admin = (
            Usuario.objects.filter(tenant_id=tenant.id, role='admin_company')
            .order_by('id')
            .first()
        )
        if admin is not None:
            tenant.dono = admin
            tenant.save()


class Migration(migrations.Migration):

    dependencies = [
        ('acesso', '0004_tenant_meta_mensal_alter_convite_papel_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='dono',
            field=models.ForeignKey(
                blank=True,
                help_text='Dono(a) do tenant — quem pode transferir a propriedade (backfill: 1o admin_company)',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='tenants_que_administra',
                to='acesso.usuario',
            ),
        ),
        migrations.RunPython(backfill_dono, migrations.RunPython.noop),
    ]
