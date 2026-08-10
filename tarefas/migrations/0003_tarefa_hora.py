from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tarefas', '0002_rename_criado_em_tarefa_created_at_tarefa_updated_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='tarefa',
            name='hora',
            field=models.TimeField(blank=True, null=True),
        ),
    ]
