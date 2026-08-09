import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('acesso', '0005_tenant_dono'),
        ('contatos', '0007_negocio_deal'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tarefa',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.TextField()),
                ('descricao', models.TextField(blank=True, default='')),
                ('prioridade', models.TextField(choices=[('baixa', 'Baixa'), ('media', 'Média'), ('alta', 'Alta')], default='media')),
                ('vencimento', models.DateField(blank=True, null=True)),
                ('concluida', models.BooleanField(default=False)),
                ('concluida_em', models.DateTimeField(blank=True, null=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(db_column='tenant_id', on_delete=django.db.models.deletion.CASCADE, related_name='tarefas', to='acesso.tenant')),
                ('contato', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tarefas', to='contatos.contato')),
                ('criado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tarefas_criadas', to='acesso.usuario')),
                ('responsavel', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tarefas', to='acesso.usuario')),
            ],
            options={
                'db_table': 'tarefas',
                'ordering': ['concluida', 'vencimento', 'id'],
            },
        ),
    ]
