"""Torna o catálogo de ritos global (sem tenant).

Os ritos são um catálogo compartilhado, como os graus: não pertencem a um
tenant. A migration remove o vínculo, descarta duplicatas por nome (o que
sobrar de tenants diferentes vira um único registro) e cria a unicidade
global em `nome`.
"""

from django.db import migrations, models


def deduplicar_ritos(apps, schema_editor):
    """Mantém um único registro por nome antes de criar o índice global."""
    Rito = apps.get_model('contatos', 'Rito')
    vistos = set()
    for rito in Rito.objects.order_by('id'):
        if rito.nome in vistos:
            rito.delete()
        else:
            vistos.add(rito.nome)


class Migration(migrations.Migration):

    dependencies = [
        ('contatos', '0029_membro_nome_historico'),
    ]

    operations = [
        migrations.RunPython(deduplicar_ritos, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='rito',
            name='rito_tenant_nome_unico',
        ),
        migrations.RemoveField(
            model_name='rito',
            name='tenant',
        ),
        migrations.AddConstraint(
            model_name='rito',
            constraint=models.UniqueConstraint(
                fields=('nome',), name='rito_nome_unico',
            ),
        ),
    ]
