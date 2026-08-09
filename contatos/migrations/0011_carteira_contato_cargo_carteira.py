"""Cria o modelo Carteira e os campos `cargo` e `carteira` no Contato.

Sprint 3 do PRD HAZON — Gestão de bases: carteiras (3.1), cargo no cliente
(3.2.7) e associação cliente -> carteira (3.2.2).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('acesso', '0008_alter_convite_options_and_more'),
        ('contatos', '0010_alter_movimentacao_options_alter_nota_options_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Carteira',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=120)),
                ('descricao', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(blank=True, db_column='tenant_id', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='carteiras', to='acesso.tenant')),
            ],
            options={
                'db_table': 'carteiras',
                'ordering': ['nome'],
            },
        ),
        migrations.AddField(
            model_name='contato',
            name='cargo',
            field=models.CharField(blank=True, default='', max_length=80),
        ),
        migrations.AddField(
            model_name='contato',
            name='carteira',
            field=models.ForeignKey(blank=True, db_column='carteira_id', help_text='Carteira da operação a que o contato pertence', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='contatos', to='contatos.carteira'),
        ),
        migrations.AddConstraint(
            model_name='carteira',
            constraint=models.UniqueConstraint(fields=('nome', 'tenant'), name='carteira_nome_tenant_unico'),
        ),
    ]
