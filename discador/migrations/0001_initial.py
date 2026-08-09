"""Migração inicial do app 'discador' — Fila, Chamada e Script (PRD Sprint 5)."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contatos', '0011_carteira_contato_cargo_carteira'),
        ('acesso', '0009_alter_usuario_role'),
    ]

    operations = [
        migrations.CreateModel(
            name='Script',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=120)),
                ('descricao', models.TextField(blank=True, default='')),
                ('conteudo', models.TextField(help_text='Passos do roteiro — uma etapa por linha (use "- " para marcar tópicos)')),
                ('ativa', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(blank=True, db_column='tenant_id', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='scripts', to='acesso.tenant')),
            ],
            options={
                'db_table': 'scripts',
                'ordering': ['nome'],
            },
        ),
        migrations.CreateModel(
            name='Fila',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=120)),
                ('descricao', models.TextField(blank=True, default='')),
                ('ordem', models.CharField(choices=[('score', 'Prioridade (lead score)'), ('criacao_asc', 'Mais antigos primeiro'), ('criacao_desc', 'Mais recentes primeiro')], default='score', max_length=20)),
                ('ativa', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('carteira', models.ForeignKey(blank=True, db_column='carteira_id', help_text='Carteira da operação — fonte dos contatos da fila', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='filas', to='contatos.carteira')),
                ('script', models.ForeignKey(blank=True, db_column='script_id', help_text='Roteiro exibido ao operador durante a chamada', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='filas', to='discador.script')),
                ('tenant', models.ForeignKey(blank=True, db_column='tenant_id', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='filas', to='acesso.tenant')),
            ],
            options={
                'db_table': 'filas',
                'ordering': ['nome'],
            },
        ),
        migrations.CreateModel(
            name='Chamada',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('discada', 'Discada'), ('realizada', 'Realizada'), ('ocupado', 'Ocupado'), ('nao_atendeu', 'Não atendeu'), ('retornar', 'Retornar depois'), ('sem_interesse', 'Sem interesse'), ('acordo', 'Acordo'), ('erro', 'Erro / indisponível')], default='discada', max_length=20)),
                ('observacao', models.TextField(blank=True, default='')),
                ('retorno_em', models.DateTimeField(blank=True, help_text='Data/hora para retornar', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('contato', models.ForeignKey(db_column='contato_id', on_delete=django.db.models.deletion.CASCADE, related_name='chamadas', to='contatos.contato')),
                ('fila', models.ForeignKey(db_column='fila_id', on_delete=django.db.models.deletion.CASCADE, related_name='chamadas', to='discador.fila')),
                ('operador', models.ForeignKey(blank=True, db_column='operador_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='chamadas', to='acesso.usuario')),
                ('tenant', models.ForeignKey(blank=True, db_column='tenant_id', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='chamadas', to='acesso.tenant')),
            ],
            options={
                'db_table': 'chamadas',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='script',
            constraint=models.UniqueConstraint(fields=('nome', 'tenant'), name='script_nome_tenant_unico'),
        ),
        migrations.AddConstraint(
            model_name='fila',
            constraint=models.UniqueConstraint(fields=('nome', 'tenant'), name='fila_nome_tenant_unico'),
        ),
    ]
