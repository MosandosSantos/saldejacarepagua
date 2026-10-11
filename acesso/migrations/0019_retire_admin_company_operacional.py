from django.db import migrations, models


def migrar_papeis_retirados(apps, schema_editor):
    Usuario = apps.get_model('acesso', 'Usuario')
    Convite = apps.get_model('acesso', 'Convite')
    database = schema_editor.connection.alias

    Usuario.objects.using(database).filter(
        role__in=('admin_company', 'operacional'),
    ).update(role='viewer')
    Usuario.objects.using(database).filter(
        role='admin_saas',
        tenant__isnull=False,
    ).update(tenant=None)
    Convite.objects.using(database).filter(
        papel__in=('admin_company', 'operacional'),
        usado_em__isnull=True,
        cancelado_em__isnull=True,
    ).update(papel='viewer')


class Migration(migrations.Migration):

    dependencies = [
        ('acesso', '0018_usuario_loja_id'),
    ]

    operations = [
        migrations.RunPython(migrar_papeis_retirados, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='usuario',
            name='role',
            field=models.TextField(choices=[
                ('admin_saas', 'Admin SaaS'),
                ('viewer', 'Somente leitura'),
                ('grande_prior', 'Grande Prior'),
                ('grande_chanceler', 'Grande Chanceler'),
                ('grande_tesoureiro', 'Grande Tesoureiro'),
                ('grande_secretario', 'Grande Secretário'),
                ('prefeito', 'Prefeito'),
                ('deputado_mestre', 'Deputado Mestre'),
            ]),
        ),
        migrations.AlterField(
            model_name='convite',
            name='papel',
            field=models.TextField(choices=[('viewer', 'viewer')]),
        ),
    ]
