from django.db import migrations, models
import django.db.models.deletion


CATALOGO_TIPOS = [
    ('Sessão Magna', '#3b82f6'),
    ('Assembleia Geral', '#22c55e'),
    ('Apresentação', '#eab308'),
    ('Elevação', '#a855f7'),
    ('Instalação', '#f97316'),
    ('Aula', '#06b6d4'),
    ('Outro', '#6b7280'),
]


def semear_tipos(apps, schema_editor):
    TipoEvento = apps.get_model('agenda', 'TipoEvento')
    for nome, cor in CATALOGO_TIPOS:
        TipoEvento.objects.get_or_create(nome=nome, defaults={'cor': cor})


def remover_tipos(apps, schema_editor):
    TipoEvento = apps.get_model('agenda', 'TipoEvento')
    TipoEvento.objects.filter(nome__in=[n for n, _ in CATALOGO_TIPOS]).delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('acesso', '0021_alter_usuario_role'),
        ('contatos', '0017_loja_membro_locais'),
    ]

    operations = [
        migrations.CreateModel(
            name='TipoEvento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=80, unique=True)),
                ('cor', models.CharField(default='#3b82f6', max_length=7)),
            ],
            options={
                'db_table': 'agenda_tipos_evento',
                'ordering': ['nome'],
            },
        ),
        migrations.CreateModel(
            name='EventoAgenda',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=200)),
                ('data_hora', models.DateTimeField()),
                ('local', models.CharField(blank=True, default='', max_length=255)),
                ('descricao', models.TextField(blank=True, default='')),
                ('google_event_id', models.CharField(blank=True, default='', max_length=120)),
                ('lembrete_48_enviado_em', models.DateTimeField(blank=True, null=True)),
                ('lembrete_24_enviado_em', models.DateTimeField(blank=True, null=True)),
                ('criado_por', models.ForeignKey(blank=True, db_column='criado_por_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='agenda_eventos_criados', to='acesso.usuario')),
                ('loja', models.ForeignKey(db_column='loja_id', on_delete=django.db.models.deletion.PROTECT, related_name='eventos_agenda', to='contatos.Loja')),
                ('tipo', models.ForeignKey(db_column='tipo_id', on_delete=django.db.models.deletion.PROTECT, related_name='eventos', to='agenda.tipoevento')),
                ('tenant', models.ForeignKey(db_column='tenant_id', on_delete=django.db.models.deletion.CASCADE, related_name='eventos_agenda', to='acesso.tenant')),
            ],
            options={
                'db_table': 'agenda_eventos',
                'ordering': ['data_hora'],
            },
        ),
        migrations.AddIndex(
            model_name='eventoagenda',
            index=models.Index(fields=['data_hora'], name='agenda_eventos_data_hora'),
        ),
        migrations.CreateModel(
            name='PresencaEvento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('estado', models.CharField(choices=[('PRESENTE', 'Presente'), ('AUSENTE', 'Ausente'), ('JUSTIFICADO', 'Justificado')], max_length=12)),
                ('justificativa', models.CharField(blank=True, default='', max_length=255)),
                ('registrado_em', models.DateTimeField(auto_now=True)),
                ('evento', models.ForeignKey(db_column='evento_id', on_delete=django.db.models.deletion.CASCADE, related_name='presencas', to='agenda.eventoagenda')),
                ('membro', models.ForeignKey(db_column='membro_id', on_delete=django.db.models.deletion.CASCADE, related_name='presencas', to='contatos.membro')),
                ('registrado_por', models.ForeignKey(blank=True, db_column='registrado_por_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='presencas_registradas', to='acesso.usuario')),
            ],
            options={
                'db_table': 'agenda_presencas',
                'ordering': ['evento', 'membro'],
            },
        ),
        migrations.AddConstraint(
            model_name='presencaevento',
            constraint=models.UniqueConstraint(fields=('evento', 'membro'), name='presenca_evento_membro_unica'),
        ),
        migrations.RunPython(semear_tipos, remover_tipos),
    ]
