"""Modelos do app 'acordos' — simulação financeira, acordos e PIX (PRD Sprint 6).

O simulador aplica as regras de desconto da empresa (RegraDesconto) ao valor
original da dívida e gera o Acordo; o PIX (BR Code estático) é montado com a
chave da empresa e o valor do acordo. Tudo escopado por tenant.
"""

from decimal import Decimal

from django.db import models

MODALIDADES = [
    ('vista', 'À vista'),
    ('parcelado', 'Parcelado'),
]

STATUS_ACORDO = [
    ('proposta', 'Proposta'),
    ('aceito', 'Aceito'),
    ('pix_gerado', 'PIX gerado'),
    ('enviado', 'Enviado'),
    ('pago', 'Pago'),
    ('recusado', 'Recusado'),
]


class RegraDesconto(models.Model):
    """Regra de desconto por modalidade + nº de parcelas (configurável por empresa).

    Ex.: à vista com 1 parcela → 30%; parcelado em 3x → 15%. O percentual é
    aplicado sobre o valor original (desconto progressivo por prazo).
    """

    modalidade = models.CharField(max_length=20, choices=MODALIDADES)
    parcelas = models.PositiveIntegerField(default=1)
    percentual = models.DecimalField(max_digits=5, decimal_places=2, help_text='Percentual de desconto (ex.: 30 = 30%)')
    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        null=True,
        blank=True,
        related_name='regras_desconto',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'regras_desconto'
        ordering = ['modalidade', 'parcelas']
        constraints = [
            models.UniqueConstraint(
                fields=['modalidade', 'parcelas', 'tenant'],
                name='regra_modalidade_parcelas_tenant_unico',
            ),
        ]

    def __str__(self):
        return f'{self.get_modalidade_display()} {self.parcelas}x — {self.percentual}%'


class Acordo(models.Model):
    """Acordo financeiro registrado — da simulação ao pagamento via PIX (6.3/6.4)."""

    contato = models.ForeignKey(
        'contatos.Contato',
        on_delete=models.CASCADE,
        db_column='contato_id',
        related_name='acordos',
    )
    chamada = models.ForeignKey(
        'discador.Chamada',
        on_delete=models.SET_NULL,
        db_column='chamada_id',
        null=True,
        blank=True,
        related_name='acordos',
        help_text='Chamada do discador que originou o acordo (integração S5 → S6)',
    )
    valor_original = models.DecimalField(max_digits=12, decimal_places=2)
    modalidade = models.CharField(max_length=20, choices=MODALIDADES)
    parcelas = models.PositiveIntegerField(default=1)
    percentual_desconto = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    desconto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valor_final = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_ACORDO, default='proposta')
    observacao = models.TextField(blank=True, default='')
    pix_payload = models.TextField(blank=True, default='', help_text='BR Code copia-e-cola gerado (se houver)')
    pago_em = models.DateTimeField(null=True, blank=True)
    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        null=True,
        blank=True,
        related_name='acordos',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'acordos'
        ordering = ['-created_at']

    def __str__(self):
        return f'Acordo {self.id} — R$ {self.valor_final} ({self.status})'

    @property
    def valor_parcela(self):
        """Valor da última parcela (as anteriores são iguais; o resto centavo fica na última).

        Mesma regra do simulador — a parcela exibida aqui bate com a proposta mostrada.
        """
        if self.parcelas <= 1:
            return self.valor_final
        base = (self.valor_final / self.parcelas).quantize(Decimal('0.01'))
        return (self.valor_final - base * (self.parcelas - 1)).quantize(Decimal('0.01'))
