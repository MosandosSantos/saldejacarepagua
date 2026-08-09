"""Modelos de automações no-code — regras que reagem a eventos do sistema.

Uma `Automacao` tem um gatilho (trigger) e uma lista ordenada de `PassoAutomacao`
(ações). Quando o evento acontece (contato novo, negócio criado, negócio movido de
etapa ou negócio parado), o motor (`automacoes.engine`) roda as ações da automação
— criar tarefa, adicionar nota, adicionar tag ou enviar e-mail — e grava um
`RegistroExecucao` para rastreio. Tudo escopado por tenant.
"""

from django.db import models

TRIGGERS = [
    ('contato_criado', 'Contato novo'),
    ('negocio_criado', 'Negócio criado'),
    ('negocio_movido', 'Negócio movido de etapa'),
    ('negocio_estagnado', 'Negócio parado (estagnado)'),
]

ACOES = [
    ('tarefa', 'Criar tarefa'),
    ('nota', 'Adicionar nota'),
    ('tag', 'Adicionar tag'),
    ('email', 'Enviar e-mail'),
]


class Automacao(models.Model):
    """Regra no-code: gatilho + lista de ações, ativável/desativável pelo admin."""

    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='automacoes',
    )
    nome = models.CharField(max_length=120)
    trigger = models.CharField(max_length=30, choices=TRIGGERS)
    # Parâmetros do gatilho: {'para_etapa': 'orcamento'} (movido),
    # {'dias': 7, 'etapa': ''} (estagnado). JSON serializado no formulário.
    parametros = models.JSONField(default=dict, blank=True)
    ativa = models.BooleanField(default=True)
    criado_por = models.ForeignKey(
        'acesso.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='automacoes_criadas',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    ultima_execucao = models.DateTimeField(null=True, blank=True)
    total_execucoes = models.IntegerField(default=0)

    class Meta:
        db_table = 'automacoes'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.nome} ({self.trigger})'


class PassoAutomacao(models.Model):
    """Uma ação de uma automação, na ordem definida pelo admin."""

    automacao = models.ForeignKey(
        Automacao,
        on_delete=models.CASCADE,
        db_column='automacao_id',
        related_name='passos',
    )
    ordem = models.IntegerField(default=0)
    acao = models.CharField(max_length=20, choices=ACOES)
    # Parâmetros da ação, conforme o tipo:
    #   tarefa: {'titulo', 'prioridade', 'vencimento_dias', 'responsavel_id'}
    #   nota:   {'texto'}
    #   tag:    {'tag'}
    #   email:  {'modelo_id'}
    parametros = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'automacoes_passos'
        ordering = ['ordem', 'id']

    def __str__(self):
        return f'{self.automacao_id}: {self.acao}'


class RegistroExecucao(models.Model):
    """Log de uma execução da automação — quem/qual negócio disparou e o resultado."""

    automacao = models.ForeignKey(
        Automacao,
        on_delete=models.CASCADE,
        db_column='automacao_id',
        related_name='execucoes',
    )
    contato = models.ForeignKey(
        'contatos.Contato',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='execucoes_automacao',
    )
    negocio = models.ForeignKey(
        'contatos.Negocio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='execucoes_automacao',
    )
    status = models.CharField(max_length=10, default='ok')  # ok | erro
    mensagem = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'automacoes_execucoes'
        ordering = ['-created_at']

    def __str__(self):
        return f'exec {self.pk} — {self.automacao_id} ({self.status})'
