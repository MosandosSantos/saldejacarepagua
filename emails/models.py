"""Modelos do e-mail marketing — ModeloEmail (templates) e EmailEnviado (rastreio)."""
import uuid

from django.db import models


class ModeloEmail(models.Model):
    """Template de e-mail do tenant, com placeholders como {{nome}}, {{procedimento}}."""

    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='modelos_email',
    )
    nome = models.TextField()
    assunto = models.TextField()
    corpo = models.TextField(
        help_text='Use {{nome}}, {{empresa}}, {{procedimento}}, {{valor}}, {{telefone}}, {{email}}'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'modelos_email'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.nome} ({self.tenant_id})'


class EmailEnviado(models.Model):
    """Registro de um e-mail enviado (ou simulado) — usado para rastreio e histórico."""

    STATUS = [
        ('pendente', 'Pendente'),
        ('enviado', 'Enviado'),
        ('simulado', 'Simulado'),
        ('erro', 'Erro'),
    ]

    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='emails_enviados',
    )
    contato = models.ForeignKey(
        'contatos.Contato',
        on_delete=models.CASCADE,
        related_name='emails_enviados',
    )
    modelo = models.ForeignKey(
        ModeloEmail,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='envios',
    )
    assunto = models.TextField()
    corpo = models.TextField()
    destinatario = models.EmailField()
    status = models.TextField(choices=STATUS, default='pendente')
    token = models.UUIDField(default=uuid.uuid4, unique=True)  # pixel de abertura
    enviado_em = models.DateTimeField(null=True, blank=True)
    aberto_em = models.DateTimeField(null=True, blank=True)
    cliques = models.IntegerField(default=0, help_text='Quantos links do e-mail foram clicados')
    ultimo_clique_em = models.DateTimeField(null=True, blank=True)
    convertido_em = models.DateTimeField(
        null=True, blank=True,
        help_text='Quando um negócio do contato fechou após contato com este e-mail',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'emails_enviados'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.destinatario} — {self.assunto}'
