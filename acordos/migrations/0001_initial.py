"""Migração inicial do app 'acordos' — RegraDesconto e Acordo (PRD Sprint 6)."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('discador', '0001_initial'),
        ('contatos', '0011_carteira_contato_cargo_carteira'),
        ('acesso', '0010_tenant_softphone'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegraDesconto',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('modalidade', models.CharField(choices=[('vista', 'À vista'), ('parcelado', 'Parcelado')], max_length=20)),
                ('parcelas', models.PositiveIntegerField(default=1)),
                ('percentual', models.DecimalField(decimal_places=2, help_text='Percentual de desconto (ex.: 30 = 30%)', max_digits=5)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tenant', models.ForeignKey(blank=True, db_column='tenant_id', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='regras_desconto', to='acesso.tenant')),
            ],
            options={
                'db_table': 'regras_desconto',
                'ordering': ['modalidade', 'parcelas'],
            },
        ),
        migrations.CreateModel(
            name='Acordo',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('valor_original', models.DecimalField(decimal_places=2, max_digits=12)),
                ('modalidade', models.CharField(choices=[('vista', 'À vista'), ('parcelado', 'Parcelado')], max_length=20)),
                ('parcelas', models.PositiveIntegerField(default=1)),
                ('percentual_desconto', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('desconto', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('valor_final', models.DecimalField(decimal_places=2, max_digits=12)),
                ('status', models.CharField(choices=[('proposta', 'Proposta'), ('aceito', 'Aceito'), ('pix_gerado', 'PIX gerado'), ('enviado', 'Enviado'), ('pago', 'Pago'), ('recusado', 'Recusado')], default='proposta', max_length=20)),
                ('observacao', models.TextField(blank=True, default='')),
                ('pix_payload', models.TextField(blank=True, default='', help_text='BR Code copia-e-cola gerado (se houver)')),
                ('pago_em', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('chamada', models.ForeignKey(blank=True, db_column='chamada_id', help_text='Chamada do discador que originou o acordo (integração S5 → S6)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='acordos', to='discador.chamada')),
                ('contato', models.ForeignKey(db_column='contato_id', on_delete=django.db.models.deletion.CASCADE, related_name='acordos', to='contatos.contato')),
                ('tenant', models.ForeignKey(blank=True, db_column='tenant_id', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='acordos', to='acesso.tenant')),
            ],
            options={
                'db_table': 'acordos',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='regradesconto',
            constraint=models.UniqueConstraint(fields=('modalidade', 'parcelas', 'tenant'), name='regra_modalidade_parcelas_tenant_unico'),
        ),
    ]
