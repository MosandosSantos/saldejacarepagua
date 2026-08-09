# Migração manual — Deals como entidade própria (Negocio).

import django.db.models.deletion
from django.db import migrations, models


def backfill_negocios(apps, schema_editor):
    """Cria um Negocio para cada contato (copiando stage/valor/tenant) e religa as movimentações."""
    Contato = apps.get_model('contatos', 'Contato')
    Negocio = apps.get_model('contatos', 'Negocio')
    Movimentacao = apps.get_model('contatos', 'Movimentacao')

    for contato in Contato.objects.all().iterator():
        negocio = Negocio.objects.create(
            contato=contato,
            titulo=contato.nome or '',
            stage=contato.stage or 'interessado',
            valor=contato.valor,
            tenant_id=contato.tenant_id,
        )
        Movimentacao.objects.filter(contato=contato).update(negocio=negocio)


class Migration(migrations.Migration):

    dependencies = [
        ('acesso', '0002_tenant_nicho'),
        ('contatos', '0006_contato_tel_normalizado_movimentacao'),
    ]

    operations = [
        migrations.CreateModel(
            name='Negocio',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(blank=True, default='', max_length=160)),
                ('stage', models.TextField()),
                ('valor', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('contato', models.OneToOneField(db_column='contato_id', on_delete=django.db.models.deletion.CASCADE, related_name='negocio', to='contatos.contato')),
                ('tenant', models.ForeignKey(blank=True, db_column='tenant_id', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='negocios', to='acesso.tenant')),
            ],
            options={
                'db_table': 'negocios',
                'ordering': ['id'],
            },
        ),
        migrations.AddField(
            model_name='movimentacao',
            name='negocio',
            field=models.ForeignKey(blank=True, db_column='negocio_id', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='movimentacoes', to='contatos.negocio'),
        ),
        migrations.RunPython(backfill_negocios, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='movimentacao',
            name='contato',
        ),
        migrations.AlterField(
            model_name='movimentacao',
            name='negocio',
            field=models.ForeignKey(db_column='negocio_id', on_delete=django.db.models.deletion.CASCADE, related_name='movimentacoes', to='contatos.negocio'),
        ),
        migrations.RemoveField(
            model_name='contato',
            name='stage',
        ),
        migrations.RemoveField(
            model_name='contato',
            name='valor',
        ),
    ]
