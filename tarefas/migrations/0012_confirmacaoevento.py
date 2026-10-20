from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('tarefas', '0011_emaileventofila'),
        ('contatos', '0028_membro_cadastro_numero'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfirmacaoEvento',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('responsavel_nome', models.CharField(blank=True, default='', max_length=200)),
                ('responsavel_email', models.CharField(max_length=254)),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('resposta', models.CharField(blank=True, choices=[('VOU', 'Vou comparecer'), ('NAO_VOU', 'Não poderei')], default='', max_length=10)),
                ('respondido_em', models.DateTimeField(blank=True, null=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('evento', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='confirmacoes', to='tarefas.evento')),
                ('membro', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='confirmacoes_evento', to='contatos.membro')),
            ],
            options={
                'db_table': 'confirmacoes_evento',
                'ordering': ['responsavel_nome', 'id'],
                'constraints': [
                    models.UniqueConstraint(fields=('evento', 'responsavel_email'), name='confirmacao_evento_destinatario_unico'),
                ],
            },
        ),
    ]
