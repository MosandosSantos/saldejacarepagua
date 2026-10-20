"""Cria as etapas Grau 19, Grau 28 e Grau 30 no Flow de Iniciação:

- Grau 19 logo após Grau 18 (ex-Comunicação): 6+ meses do grau 18;
- Grau 28 logo após Grau 22 (ex-Diploma): 4+ meses do grau 22;
- Grau 30 logo após Grau 28: 4+ meses do grau 28.

Cadência (ANCORA_TEMPO_DA_ETAPA): 18→19 (6m), 19→22 (4m), 22→28 (4m),
28→30 (4m). Idempotente por key, mesma política de get_or_create da 0004.
"""

from django.db import migrations
from django.db.models import F

# key → (nome, cor, peso, key da etapa âncora logo acima)
_NOVAS = [
    ('grau19', 'Grau 19', '#f472b6', 0.85, 'comunicacao'),
    ('grau28', 'Grau 28', '#fb923c', 0.95, 'diploma'),
    ('grau30', 'Grau 30', '#facc15', 0.98, 'grau28'),
]


def cria_etapas(apps, schema_editor):
    EtapaFunil = apps.get_model('recepcao', 'EtapaFunil')

    tenants = (
        EtapaFunil.objects.values_list('tenant_id', flat=True).distinct().iterator()
    )
    for tenant_id in tenants:
        for key, nome, cor, peso, base_key in _NOVAS:
            base = EtapaFunil.objects.filter(
                tenant_id=tenant_id, key=base_key,
            ).first()
            ordem = (base.ordem + 1) if base else 1
            etapa, criada = EtapaFunil.objects.get_or_create(
                tenant_id=tenant_id,
                key=key,
                defaults={
                    'nome': nome,
                    'cor': cor,
                    'ordem': ordem,
                    'peso': peso,
                    'sistema': False,
                },
            )
            if criada:
                EtapaFunil.objects.filter(
                    tenant_id=tenant_id, ordem__gte=ordem,
                ).exclude(pk=etapa.pk).update(ordem=F('ordem') + 1)


def remove_etapas(apps, schema_editor):
    EtapaFunil = apps.get_model('recepcao', 'EtapaFunil')
    EtapaFunil.objects.filter(key__in=['grau19', 'grau28', 'grau30']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('recepcao', '0006_diploma_para_grau22'),
    ]

    operations = [
        migrations.RunPython(cria_etapas, remove_etapas),
    ]
