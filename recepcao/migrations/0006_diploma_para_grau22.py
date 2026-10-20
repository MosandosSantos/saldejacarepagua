"""Renomeia a etapa `diploma` (Diploma → Grau 22) — o marco final vira a
relação do grau 22 (todos os detentores do grau 21 com 6+ meses do grau 18).

Somente rótulos não customizados são renomeados (o nome antigo tem de bater
exatamente); etapas customizadas nunca são alteradas. Mesma política de
`adotar_nicho` (ver 0004/0005).
"""

from django.db import migrations


def renomeia_diploma(apps, schema_editor):
    EtapaFunil = apps.get_model('recepcao', 'EtapaFunil')
    EtapaFunil.objects.filter(
        key='diploma', nome='Diploma',
    ).update(nome='Grau 22')


def desfaz(apps, schema_editor):
    EtapaFunil = apps.get_model('recepcao', 'EtapaFunil')
    EtapaFunil.objects.filter(
        key='diploma', nome='Grau 22',
    ).update(nome='Diploma')


class Migration(migrations.Migration):

    dependencies = [
        ('recepcao', '0005_comunicacao_para_grau18'),
    ]

    operations = [
        migrations.RunPython(renomeia_diploma, desfaz),
    ]
