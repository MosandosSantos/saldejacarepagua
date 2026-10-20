"""Renomeia a etapa `comunicacao` (Comunicação → Grau 18) — ela entra na
cadeia de graus do Rito: a coluna lista os membros detentores do grau 17.

Somente rótulos não customizados são renomeados (o nome antigo tem de bater
exatamente); etapas customizadas nunca são alteradas. Mesma política de
`adotar_nicho` (ver 0004).
"""

from django.db import migrations


def renomeia_comunicacao(apps, schema_editor):
    EtapaFunil = apps.get_model('recepcao', 'EtapaFunil')
    EtapaFunil.objects.filter(
        key='comunicacao', nome='Comunicação',
    ).update(nome='Grau 18')


def desfaz(apps, schema_editor):
    EtapaFunil = apps.get_model('recepcao', 'EtapaFunil')
    EtapaFunil.objects.filter(
        key='comunicacao', nome='Grau 18',
    ).update(nome='Comunicação')


class Migration(migrations.Migration):

    dependencies = [
        ('recepcao', '0004_renomeia_etapas_graus'),
    ]

    operations = [
        migrations.RunPython(renomeia_comunicacao, desfaz),
    ]
