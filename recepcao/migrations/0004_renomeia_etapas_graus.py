"""Renomeia as etapas do funil para os graus (Suplica→Grau 4, Pagamento→Grau 9,
Iniciação→Grau 14) e cria a etapa Grau 15 logo após Grau 14 em cada tenant.

Somente rótulos não customizados são renomeados (o nome antigo tem de bater
exatamente); etapas customizadas nunca são alteradas. Mesma política de
`adotar_nicho`.
"""

from django.db import migrations
from django.db.models import F

# key → (nome antigo, nome novo)
_RENOMES = {
    'suplica': ('Suplica', 'Grau 4'),
    'pagamento': ('Pagamento', 'Grau 9'),
    'iniciacao': ('Iniciação', 'Grau 14'),
}

_GRAU15 = {'nome': 'Grau 15', 'cor': '#c084fc', 'peso': 0.7}


def renomeia_e_cria_grau15(apps, schema_editor):
    EtapaFunil = apps.get_model('recepcao', 'EtapaFunil')

    for etapa in EtapaFunil.objects.all():
        alvo = _RENOMES.get(etapa.key)
        if alvo and etapa.nome == alvo[0]:
            etapa.nome = alvo[1]
            etapa.save(update_fields=['nome'])

    tenants = (
        EtapaFunil.objects.values_list('tenant_id', flat=True).distinct().iterator()
    )
    for tenant_id in tenants:
        base = EtapaFunil.objects.filter(tenant_id=tenant_id, key='iniciacao').first()
        ordem = (base.ordem + 1) if base else 1
        etapa, criada = EtapaFunil.objects.get_or_create(
            tenant_id=tenant_id,
            key='grau15',
            defaults={
                'nome': _GRAU15['nome'],
                'cor': _GRAU15['cor'],
                'ordem': ordem,
                'peso': _GRAU15['peso'],
                'sistema': False,
            },
        )
        if criada:
            EtapaFunil.objects.filter(
                tenant_id=tenant_id, ordem__gte=ordem,
            ).exclude(pk=etapa.pk).update(ordem=F('ordem') + 1)


def volta_etapas(apps, schema_editor):
    EtapaFunil = apps.get_model('recepcao', 'EtapaFunil')

    for etapa in EtapaFunil.objects.all():
        alvo = _RENOMES.get(etapa.key)
        if alvo and etapa.nome == alvo[1]:
            etapa.nome = alvo[0]
            etapa.save(update_fields=['nome'])

    EtapaFunil.objects.filter(key='grau15').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('recepcao', '0003_alter_etapafunil_id'),
    ]

    operations = [
        migrations.RunPython(renomeia_e_cria_grau15, volta_etapas),
    ]
