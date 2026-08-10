from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('acesso', '0012_remove_tenant_pix'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                'DROP TABLE IF EXISTS acordos;',
                'DROP TABLE IF EXISTS acordos_regradesconto;',
                "DELETE FROM django_migrations WHERE app='acordos';",
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
