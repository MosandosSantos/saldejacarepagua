"""Adiciona multitenancia: coluna tenant_id em contatos + backfill dos dados atuais."""
from django.db import migrations, models


def backfill_tenant_padrao(apps, schema_editor):
    """Atribui os contatos existentes (sem tenant) a um tenant padrao de demonstracao."""
    Tenant = apps.get_model('acesso', 'Tenant')
    Contato = apps.get_model('contatos', 'Contato')

    tenant, _ = Tenant.objects.get_or_create(
        slug='clinica-aurora',
        defaults={'nome': 'Clínica Aurora (demonstração)'},
    )
    Contato.objects.filter(tenant__isnull=True).update(tenant_id=tenant.id)


class Migration(migrations.Migration):
    dependencies = [
        ('acesso', '0001_initial'),
        ('contatos', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='contato',
            name='tenant',
            field=models.ForeignKey(
                'acesso.Tenant',
                db_column='tenant_id',
                null=True,
                blank=True,
                on_delete=models.CASCADE,
                related_name='contatos',
            ),
        ),
        migrations.RunPython(backfill_tenant_padrao, migrations.RunPython.noop),
    ]
