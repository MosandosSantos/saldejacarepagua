"""Modelo EtapaFunil — pipeline de vendas configurável por tenant.

Antes, as etapas eram fixas em core.dominio.STAGES e o nicho apenas re-rotulava
os nomes. Agora cada tenant tem as próprias etapas (nome, cor, ordem e
probabilidade de fechamento), salvas em `etapas_funil`. A `key` continua sendo o
valor gravado em Negocio.stage — as etapas de sistema `fechado`/`perdido` podem
ser renomeadas/recoloridas, mas não excluídas (o dashboard depende delas).
"""

from decimal import Decimal

from django.db import models

from core.dominio import NICHO_PADRAO, PESOS_ETAPA, stages_do_nicho

ETAPAS_SISTEMA = ('fechado', 'perdido')
PESO_NOVO = Decimal('0.500')


class EtapaFunil(models.Model):
    """Etapa do funil de vendas do tenant."""

    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='etapas',
    )
    key = models.CharField(max_length=40, help_text='Chave interna salva em Negocio.stage')
    nome = models.TextField()
    cor = models.TextField(default='#94a3b8')
    ordem = models.IntegerField(default=0)
    peso = models.DecimalField(
        max_digits=4, decimal_places=3, default=PESO_NOVO,
        help_text='Probabilidade de fechamento (0 a 1) — base da receita projetada',
    )
    sistema = models.BooleanField(
        default=False,
        help_text='Etapa fixa do sistema (fechado/perdido) — não pode ser excluída',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'etapas_funil'
        ordering = ['ordem', 'id']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'key'], name='etapa_funil_unica_por_tenant'),
        ]

    def __str__(self):
        return f'{self.nome} ({self.key})'


def _semeia_etapas(tenant_id, nicho=None):
    """Cria as etapas padrão do nicho para o tenant (idempotente por key)."""
    if tenant_id is None:
        return []
    for i, s in enumerate(stages_do_nicho(nicho or NICHO_PADRAO)):
        EtapaFunil.objects.get_or_create(
            tenant_id=tenant_id, key=s['key'],
            defaults={
                'nome': s['name'],
                'cor': s['color'],
                'ordem': i,
                'peso': PESOS_ETAPA.get(s['key'], PESO_NOVO),
                'sistema': s['key'] in ETAPAS_SISTEMA,
            },
        )


def garantir_etapas(tenant_id, nicho=None):
    """Garante que o tenant tenha etapas gravadas (semeia se vazio)."""
    if tenant_id is None:
        return
    if not EtapaFunil.objects.filter(tenant_id=tenant_id).exists():
        _semeia_etapas(tenant_id, nicho)


def adotar_nicho(tenant_id, nicho):
    """Usado no onboarding: cria as etapas do nicho escolhido e, para tenants
    semeados antes com o nicho padrão (ex.: backfill antigo), renomeia as etapas
    ainda intocadas para o novo nicho. Etapas customizadas nunca são alteradas.
    """
    if tenant_id is None:
        return
    antigos = {s['key']: s['name'] for s in stages_do_nicho(NICHO_PADRAO)}
    for i, s in enumerate(stages_do_nicho(nicho or NICHO_PADRAO)):
        etapa, criada = EtapaFunil.objects.get_or_create(
            tenant_id=tenant_id, key=s['key'],
            defaults={
                'nome': s['name'], 'cor': s['color'], 'ordem': i,
                'peso': PESOS_ETAPA.get(s['key'], PESO_NOVO),
                'sistema': s['key'] in ETAPAS_SISTEMA,
            },
        )
        if not criada and etapa.nome == antigos.get(s['key']):
            # ainda com o rótulo do nicho padrão → adota o rótulo do nicho escolhido
            etapa.nome = s['name']
            etapa.cor = s['color']
            etapa.save(update_fields=['nome', 'cor'])


def etapas_do_tenant(tenant_id, nicho=None):
    """Lista de dicts {key, name, color, peso} das etapas do tenant.

    Sem tenant (admin_saas) ou tenant ainda sem pipeline próprio, devolve as
    etapas padrão do nicho — o sistema nunca fica sem colunas no funil.
    """
    if tenant_id is None:
        return stages_do_nicho(nicho or NICHO_PADRAO)
    etapas = list(EtapaFunil.objects.filter(tenant_id=tenant_id))
    if not etapas:
        return stages_do_nicho(nicho or NICHO_PADRAO)
    return [
        {'key': e.key, 'name': e.nome, 'color': e.cor, 'peso': float(e.peso)}
        for e in etapas
    ]


def etapa_map_do_tenant(tenant_id, nicho=None):
    """dict key → etapa (para decorar fichas, validar e ponderar)."""
    return {s['key']: s for s in etapas_do_tenant(tenant_id, nicho)}
