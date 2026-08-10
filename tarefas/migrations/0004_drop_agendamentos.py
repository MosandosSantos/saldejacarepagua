from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tarefas', '0003_tarefa_hora'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                'DROP TABLE IF EXISTS agendamentos;',
                "DELETE FROM django_migrations WHERE app='agendamentos';",
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
