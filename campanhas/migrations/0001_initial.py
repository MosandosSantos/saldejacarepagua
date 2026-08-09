"""Migração inicial do app 'campanhas' — modelo Campanha (S4 do PRD HAZON, 4.1)."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('acesso', '0009_alter_usuario_role'),
    ]

    operations = [
        migrations.CreateModel(
            name='Campanha',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=120)),
                ('descricao', models.TextField(blank=True, default='')),
                ('canal', models.CharField(choices=[('email', 'E-mail'), ('whatsapp', 'WhatsApp'), ('telefone', 'Telefone')], default='email', max_length=20)),
                ('ativa', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(blank=True, db_column='tenant_id', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='campanhas', to='acesso.tenant')),
            ],
            options={
                'db_table': 'campanhas',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='campanha',
            constraint=models.UniqueConstraint(fields=('nome', 'tenant'), name='campanha_nome_tenant_unico'),
        ),
    ]
