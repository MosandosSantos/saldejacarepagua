"""Modelo do app 'campanhas' — Campanha (estrutura por canal, escopada por tenant).

Sprint 4 do PRD HAZON (4.1 — Estrutura de campanhas): criar estrutura de campanha,
associar à empresa, definir canal (e-mail/WhatsApp/telefone), listar e detalhar.
O WhatsApp/telefone dependem de integrações externas (decisão de provedor); o canal
de e-mail já dispara de verdade usando o app `emails` (modelos + rastreio).
"""

from django.db import models


class Campanha(models.Model):
    """Campanha de comunicação — nome, canal e status, escopada por tenant."""

    CANAIS = [
        ('email', 'E-mail'),
        ('whatsapp', 'WhatsApp'),
        ('telefone', 'Telefone'),
    ]

    nome = models.CharField(max_length=120)
    descricao = models.TextField(blank=True, default='')
    canal = models.CharField(max_length=20, choices=CANAIS, default='email')
    ativa = models.BooleanField(default=True)
    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='campanhas',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'campanhas'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['nome', 'tenant'], name='campanha_nome_tenant_unico'),
        ]

    def __str__(self):
        return f'{self.nome} ({self.get_canal_display()})'
