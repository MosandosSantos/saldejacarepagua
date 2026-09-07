from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models

from core.dominio import PESOS_ETAPA, stages_do_nicho

ETAPAS_SISTEMA = ('fechado', 'perdido')
PESO_NOVO = Decimal('0.500')


def semeia_etapas(apps, schema_editor):
    """Backfill: cada tenant existente ganha as etapas padrão do seu nicho.

    Tenants sem nicho (ainda não passaram pelo onboarding) são pulados — o
    onboarding semeia com o nicho que o dono escolher.
    """
    Tenant = apps.get_model('acesso', 'Tenant')
    Etapa = apps.get_model('recepcao', 'EtapaFunil')
    for t in Tenant.objects.all().iterator():
        if not t.nicho:
            continue
        for i, s in enumerate(stages_do_nicho(t.nicho)):
            Etapa.objects.get_or_create(
                tenant_id=t.id, key=s['key'],
                defaults={
                    'nome': s['name'],
                    'cor': s['color'],
                    'ordem': i,
                    'peso': PESOS_ETAPA.get(s['key'], PESO_NOVO),
                    'sistema': s['key'] in ETAPAS_SISTEMA,
                },
            )


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('acesso', '0005_tenant_dono'),
    ]

    operations = [
        migrations.CreateModel(
            name='EtapaFunil',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(help_text='Chave interna salva em Negocio.stage', max_length=40)),
                ('nome', models.TextField()),
                ('cor', models.TextField(default='#94a3b8')),
                ('ordem', models.IntegerField(default=0)),
                ('peso', models.DecimalField(decimal_places=3, default=Decimal('0.500'), help_text='Probabilidade de fechamento (0 a 1) — base da receita projetada', max_digits=4)),
                ('sistema', models.BooleanField(default=False, help_text='Etapa fixa do sistema (fechado/perdido) — não pode ser excluída')),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(db_column='tenant_id', on_delete=django.db.models.deletion.CASCADE, related_name='etapas', to='acesso.tenant')),
            ],
            options={
                'db_table': 'etapas_funil',
                'ordering': ['ordem', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='etapafunil',
            constraint=models.UniqueConstraint(fields=('tenant', 'key'), name='etapa_funil_unica_por_tenant'),
        ),
        migrations.RunPython(semeia_etapas, migrations.RunPython.noop),
    ]
