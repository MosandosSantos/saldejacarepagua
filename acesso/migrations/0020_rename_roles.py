from django.db import migrations


def rename_roles(apps, schema_editor):
    Usuario = apps.get_model('acesso', 'Usuario')
    mapping = {
        'grande_prior': 'ADM',
        'grande_tesoureiro': 'tesoureiro',
        'grande_secretario': 'secretario',
        'prefeito': 'delegado',
        'deputado_mestre': 'presidente_corpo',
    }
    for old, new in mapping.items():
        Usuario.objects.filter(role=old).update(role=new)


def reverse_rename(apps, schema_editor):
    Usuario = apps.get_model('acesso', 'Usuario')
    mapping = {
        'ADM': 'grande_prior',
        'tesoureiro': 'grande_tesoureiro',
        'secretario': 'grande_secretario',
        'delegado': 'prefeito',
        'presidente_corpo': 'deputado_mestre',
    }
    for new, old in mapping.items():
        Usuario.objects.filter(role=new).update(role=old)


class Migration(migrations.Migration):
    dependencies = [
        ('acesso', '0019_retire_admin_company_operacional'),
    ]

    operations = [
        migrations.RunPython(rename_roles, reverse_rename),
    ]
