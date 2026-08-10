"""Modelos do app 'discador' — Fila, Chamada e Script (Nation Dialer, PRD Sprint 5).

A fila organiza os contatos telefônicos da operação (5.1); a chamada registra o
início e o resultado de cada ligação (5.2); o script é o roteiro de atendimento
exibido durante a chamada (5.3). Tudo escopado por tenant.
"""

from django.db import models


class Script(models.Model):
    """Roteiro de atendimento (SPIN Selling e afins) associado a uma operação.

    O script é reutilizável: uma fila o referencia para exibir durante a chamada.
    """

    nome = models.CharField(max_length=120)
    descricao = models.TextField(blank=True, default='')
    conteudo = models.TextField(
        help_text='Passos do roteiro — uma etapa por linha (use "- " para marcar tópicos)'
    )
    ativa = models.BooleanField(default=True)
    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='scripts',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'scripts'
        ordering = ['nome']
        constraints = [
            models.UniqueConstraint(fields=['nome', 'tenant'], name='script_nome_tenant_unico'),
        ]

    def __str__(self):
        return self.nome


class Fila(models.Model):
    """Fila de discagem — organiza os contatos telefônicos de uma operação.

    Os contatos da fila vêm da carteira associada (quando houver) ou de todos os
    contatos do tenant com telefone válido; a ordem da lista segue o campo `ordem`.
    """

    ORDENS = [
        ('score', 'Prioridade (lead score)'),
        ('criacao_asc', 'Mais antigos primeiro'),
        ('criacao_desc', 'Mais recentes primeiro'),
    ]

    nome = models.CharField(max_length=120)
    descricao = models.TextField(blank=True, default='')
    carteira = models.ForeignKey(
        'contatos.Carteira',
        on_delete=models.SET_NULL,
        db_column='carteira_id',
        null=True,
        blank=True,
        related_name='filas',
        help_text='Carteira da operação — fonte dos contatos da fila',
    )
    script = models.ForeignKey(
        Script,
        on_delete=models.SET_NULL,
        db_column='script_id',
        null=True,
        blank=True,
        related_name='filas',
        help_text='Roteiro exibido ao operador durante a chamada',
    )
    ordem = models.CharField(max_length=20, choices=ORDENS, default='score')
    ativa = models.BooleanField(default=True)
    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='filas',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'filas'
        ordering = ['nome']
        constraints = [
            models.UniqueConstraint(fields=['nome', 'tenant'], name='fila_nome_tenant_unico'),
        ]

    def __str__(self):
        return self.nome

    def contatos(self):
        """Contatos da fila: da carteira associada (ou todos do tenant) com telefone válido."""
        from contatos.models import Contato

        qs = Contato.objects.filter(tenant_id=self.tenant_id)
        if self.carteira_id:
            qs = qs.filter(carteira_id=self.carteira_id)
        qs = qs.exclude(tel_normalizado='')
        if self.ordem == 'criacao_asc':
            return qs.order_by('created_at', 'id')
        if self.ordem == 'criacao_desc':
            return qs.order_by('-created_at', 'id')
        return qs.order_by('-lead_score', 'id')

    def script_ativo(self):
        """Script da fila quando ativo (nenhum fallback — o script é definido na própria fila)."""
        if self.script_id and self.script.ativa:
            return self.script
        return None


class Chamada(models.Model):
    """Registro de uma ligação — início (discada) e resultado (5.2.5)."""

    STATUS = [
        ('discada', 'Discada'),
        ('realizada', 'Realizada'),
        ('ocupado', 'Ocupado'),
        ('nao_atendeu', 'Não atendeu'),
        ('retornar', 'Retornar depois'),
        ('sem_interesse', 'Sem interesse'),
        ('acordo', 'Acordo'),
        ('erro', 'Erro / indisponível'),
    ]

    fila = models.ForeignKey(
        Fila,
        on_delete=models.CASCADE,
        db_column='fila_id',
        related_name='chamadas',
    )
    contato = models.ForeignKey(
        'contatos.Contato',
        on_delete=models.CASCADE,
        db_column='contato_id',
        related_name='chamadas',
    )
    operador = models.ForeignKey(
        'acesso.Usuario',
        on_delete=models.SET_NULL,
        db_column='operador_id',
        null=True,
        blank=True,
        related_name='chamadas',
    )
    status = models.CharField(max_length=20, choices=STATUS, default='discada')
    observacao = models.TextField(blank=True, default='')
    retorno_em = models.DateTimeField(null=True, blank=True, help_text='Data/hora para retornar')
    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='chamadas',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'chamadas'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant_id', 'status'], name='cha_tenant_status_idx'),
        ]

    def __str__(self):
        return f'Chamada {self.id} — contato {self.contato_id} ({self.status})'
