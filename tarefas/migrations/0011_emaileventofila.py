from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tarefas', '0010_presencaevento'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailEventoFila',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('destinatario_nome', models.CharField(blank=True, default='', max_length=200)),
                ('destinatario_email', models.CharField(max_length=254)),
                ('situacao', models.CharField(choices=[('PENDENTE', 'Pendente'), ('ENVIADO', 'Enviado'), ('ERRO', 'Erro')], default='PENDENTE', max_length=10)),
                ('tentativas', models.PositiveIntegerField(default=0)),
                ('erro', models.TextField(blank=True, default='')),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('enviado_em', models.DateTimeField(blank=True, null=True)),
                ('evento', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='fila_emails', to='tarefas.evento')),
            ],
            options={
                'db_table': 'email_evento_fila',
                'ordering': ['id'],
            },
        ),
        migrations.AddIndex(
            model_name='emaileventofila',
            index=models.Index(fields=['situacao', 'id'], name='email_even_situac__d7a9b5_idx'),
        ),
    ]
