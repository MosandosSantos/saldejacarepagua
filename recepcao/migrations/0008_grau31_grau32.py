"""Cria as etapas Grau 31 e Grau 32 (Consistório) no Flow de Iniciação:

- Grau 31 logo após Grau 30: 6+ meses do grau 30;
- Grau 32 logo após Grau 31: 3+ meses do grau 31.

Idempotente por key, mesma política de get_or_create das migrations 0004/0007.
Tenants sem etapas gravadas ficam para o seed automático de dominio.STAGES.
"""

from django.db import migrations
from django.db.models import F

# key → (nome, cor, peso, key da etapa âncora logo acima)
_NOVAS = [
    ('grau31', 'Grau 31', '#fda4af', 0.99, 'grau30'),
    ('grau32', 'Grau 32', '#e879f9', 1.00, 'grau31'),
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
    EtapaFunil.objects.filter(key__in=['grau31', 'grau32']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('recepcao', '0007_grau19_grau28_grau30'),
    ]

    operations = [
        migrations.RunPython(cria_etapas, remove_etapas),
    ]
