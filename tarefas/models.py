"""Modelo Tarefa — follow-ups e lembretes do time, escopados por tenant.

Cada tarefa tem título, descrição, contato (opcional), responsável (opcional),
prioridade, vencimento e status. O vencimento alimenta os lembretes: atrasadas,
de hoje, próximas — com badge no header e alerta no dashboard.
"""

import uuid

from django.db import models
from django.db.models import Count, Q
from django.utils import timezone

PRIORIDADES = [
    ('baixa', 'Baixa'),
    ('media', 'Média'),
    ('alta', 'Alta'),
]

PRIORIDADE_CORES = {
    'baixa': '#94a3b8',
    'media': '#74b3c6',
    'alta': '#fbbf24',
}


class Tarefa(models.Model):
    """Tarefa/follow-up do time (ex.: 'Ligar pra retornar o orçamento')."""

    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='tarefas',
    )
    titulo = models.TextField()
    descricao = models.TextField(blank=True, default='')
    contato = models.ForeignKey(
        'contatos.Contato',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tarefas',
    )
    responsavel = models.ForeignKey(
        'acesso.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tarefas',
    )
    prioridade = models.TextField(choices=PRIORIDADES, default='media')
    vencimento = models.DateField(null=True, blank=True)
    hora = models.TimeField(null=True, blank=True)
    concluida = models.BooleanField(default=False)
    concluida_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(
        'acesso.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tarefas_criadas',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tarefas'
        ordering = ['concluida', 'vencimento', 'hora', 'id']
        indexes = [
            models.Index(fields=['tenant_id', 'concluida', 'vencimento'], name='tar_tenant_status_due_idx'),
        ]

    def __str__(self):
        return f'{self.titulo} ({self.tenant_id})'

    @property
    def atrasada(self):
        return bool(self.vencimento and not self.concluida and self.vencimento < timezone.localdate())


def resumo_tarefas(tenant_id):
    """Contagens para o badge do header (admin_saas = zero). Uma única query agregada."""
    if tenant_id is None:
        return {'atrasadas': 0, 'hoje': 0, 'abertas': 0}
    hoje = timezone.localdate()
    agg = (
        Tarefa.objects.filter(tenant_id=tenant_id, concluida=False)
        .aggregate(
            atrasadas=Count('id', filter=Q(vencimento__lt=hoje)),
            hoje=Count('id', filter=Q(vencimento=hoje)),
            abertas=Count('id'),
        )
    )
    return {'atrasadas': agg['atrasadas'], 'hoje': agg['hoje'], 'abertas': agg['abertas']}


def concluir_tarefa(tarefa):
    """Marca como concluída (idempotente)."""
    if not tarefa.concluida:
        tarefa.concluida = True
        tarefa.concluida_em = timezone.now()
        tarefa.save(update_fields=['concluida', 'concluida_em'])


def reabrir_tarefa(tarefa):
    """Reabre uma tarefa concluída."""
    if tarefa.concluida:
        tarefa.concluida = False
        tarefa.concluida_em = None
        tarefa.save(update_fields=['concluida', 'concluida_em'])


# ---------------------------------------------------------------------------
# Evento (sessão/reunião da loja maçonica)
# ---------------------------------------------------------------------------

TIPOS_EVENTO_SELETOR = [
    (f'iniciacao_grau_{grau}', f'Iniciação do grau {grau}')
    for grau in range(4, 33)
] + [
    ('posse', 'Posse'),
    ('outros', 'Outros'),
]

# Keep these choices so events saved before the catalog change still render
# with their original labels. They are not offered for new events.
TIPOS_EVENTO_LEGADOS = [
    ('sessao', 'Sessão'),
    ('reuniao', 'Reunião'),
    ('trabalho', 'Trabalho'),
    ('ritual', 'Ritual'),
]
TIPOS_EVENTO = TIPOS_EVENTO_SELETOR + TIPOS_EVENTO_LEGADOS


class Evento(models.Model):
    """Sessão ou reunião da loja maçonica — escopado por loja_id (UUID GPRB)."""

    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, default='')
    tipo = models.CharField(max_length=20, choices=TIPOS_EVENTO, default='sessao')
    data_inicio = models.DateTimeField()
    data_fim = models.DateTimeField()
    loja_id = models.CharField(
        max_length=36,
        help_text='UUID da loja GPRB vinculada ao evento',
    )
    criado_por = models.ForeignKey(
        'acesso.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_criados',
    )
    lembrete_enviado = models.BooleanField(
        default=False,
        help_text='True quando o lembrete de 72h já foi enviado',
    )
    google_event_id = models.CharField(
        max_length=120,
        blank=True,
        default='',
        help_text='ID do evento no Google Calendar (auto-sync)',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'eventos'
        ordering = ['data_inicio']
        indexes = [
            models.Index(fields=['loja_id', 'data_inicio'], name='evento_loja_data_idx'),
        ]

    def __str__(self):
        return f'{self.get_tipo_display()}: {self.titulo} ({self.data_inicio:%d/%m/%Y})'

    @property
    def sessao_encerrada(self):
        """True quando a sessão já terminou (fuso configurado do projeto).

        Base da regra "botão de presença só após a sessão" e do bloqueio
        de gravação de chamada antecipada.
        """
        fim = self.data_fim
        if fim is None:
            return False
        if timezone.is_naive(fim):
            fim = timezone.make_aware(fim, timezone.get_default_timezone())
        return timezone.now() >= fim


class PresencaEvento(models.Model):
    """Lista de chamada: presença (True) ou falta (False) de um membro num evento.

    Tabela auxiliar do quadro: um registro por par (evento, membro) — atualizar
    a chamada regrava o mesmo registro, nunca duplica. O percentual de presença
    do membro (exibido na tabela de membros) deriva destes registros.
    """

    evento = models.ForeignKey(
        'tarefas.Evento',
        on_delete=models.CASCADE,
        related_name='presencas',
    )
    membro = models.ForeignKey(
        'contatos.Membro',
        on_delete=models.CASCADE,
        related_name='presencas_sessoes',
    )
    presente = models.BooleanField()
    registrado_por = models.ForeignKey(
        'acesso.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='presencas_sessao_registradas',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'presencas_evento'
        ordering = ['evento', 'membro']
        constraints = [
            models.UniqueConstraint(
                fields=['evento', 'membro'],
                name='presenca_evento_membro_unico',
            ),
        ]

    def __str__(self):
        estado = 'presente' if self.presente else 'falta'
        return f'{self.membro}: {estado} em {self.evento}'


class EmailEventoFila(models.Model):
    """Fila durável de envio dos avisos de evento (envio assíncrono).

    O request grava as linhas e responde na hora; o worker (thread em
    background ou o comando `enviar_emails_eventos`) consome depois —
    o usuário nunca fica com a tela travada no SMTP.
    """

    SITUACAO_CHOICES = (
        ('PENDENTE', 'Pendente'),
        ('ENVIADO', 'Enviado'),
        ('ERRO', 'Erro'),
    )

    evento = models.ForeignKey(
        'tarefas.Evento',
        on_delete=models.CASCADE,
        related_name='fila_emails',
    )
    destinatario_nome = models.CharField(max_length=200, blank=True, default='')
    destinatario_email = models.CharField(max_length=254)
    situacao = models.CharField(max_length=10, choices=SITUACAO_CHOICES, default='PENDENTE')
    tentativas = models.PositiveIntegerField(default=0)
    erro = models.TextField(blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)
    enviado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'email_evento_fila'
        ordering = ['id']
        indexes = [
            models.Index(fields=['situacao', 'id']),
        ]

    def __str__(self):
        return f'{self.destinatario_email} — {self.situacao} (evento {self.evento_id})'


class ConfirmacaoEvento(models.Model):
    """Confirmação de presença (RSVP) por destinatário do convite.

    O token UUID é a credencial: o link por e-mail abre a página de
    confirmação (sem login) e o POST grava VOU/NAO com data da resposta.
    Reclique atualiza a resposta. Delegado do Vale confirma sem Membro.
    """

    RESPOSTA_CHOICES = (
        ('VOU', 'Vou comparecer'),
        ('NAO_VOU', 'Não poderei'),
    )

    evento = models.ForeignKey(
        'tarefas.Evento',
        on_delete=models.CASCADE,
        related_name='confirmacoes',
    )
    membro = models.ForeignKey(
        'contatos.Membro',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmacoes_evento',
    )
    responsavel_nome = models.CharField(max_length=200, blank=True, default='')
    responsavel_email = models.CharField(max_length=254)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    resposta = models.CharField(max_length=10, choices=RESPOSTA_CHOICES, blank=True, default='')
    respondido_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'confirmacoes_evento'
        ordering = ['responsavel_nome', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['evento', 'responsavel_email'],
                name='confirmacao_evento_destinatario_unico',
            ),
        ]

    def __str__(self):
        return f'{self.responsavel_email or self.responsavel_nome}: {self.resposta or "sem resposta"} ({self.evento_id})'
