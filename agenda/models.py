"""Modelos da agenda de eventos, presenças e tipos de evento."""
from django.db import models
from django.db.models.functions import Lower


class TipoEvento(models.Model):
    """Catálogo fixo de tipos de evento (compartilhado entre tenants)."""

    nome = models.CharField(max_length=80, unique=True)
    cor = models.CharField(max_length=7, default='#3b82f6')

    class Meta:
        db_table = 'agenda_tipos_evento'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class EventoAgenda(models.Model):
    """Evento da agenda, vinculado a uma loja do tenant."""

    tenant = models.ForeignKey(
        'acesso.Tenant',
        on_delete=models.CASCADE,
        db_column='tenant_id',
        related_name='eventos_agenda',
    )
    loja = models.ForeignKey(
        'contatos.Loja',
        on_delete=models.PROTECT,
        db_column='loja_id',
        related_name='eventos_agenda',
    )
    tipo = models.ForeignKey(
        'agenda.TipoEvento',
        on_delete=models.PROTECT,
        db_column='tipo_id',
        related_name='eventos',
    )
    titulo = models.CharField(max_length=200)
    data_hora = models.DateTimeField()
    local = models.CharField(max_length=255, blank=True, default='')
    descricao = models.TextField(blank=True, default='')
    criado_por = models.ForeignKey(
        'acesso.Usuario',
        on_delete=models.SET_NULL,
        db_column='criado_por_id',
        related_name='agenda_eventos_criados',
        null=True, blank=True,
    )
    google_event_id = models.CharField(max_length=120, blank=True, default='')
    lembrete_48_enviado_em = models.DateTimeField(null=True, blank=True)
    lembrete_24_enviado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'agenda_eventos'
        ordering = ['data_hora']
        indexes = [models.Index(fields=['data_hora'], name='agenda_eventos_data_hora')]

    def __str__(self):
        return self.titulo


class PresencaEvento(models.Model):
    """Presença de um membro em um evento (registrada após o evento)."""

    ESTADOS = [
        ('PRESENTE', 'Presente'),
        ('AUSENTE', 'Ausente'),
        ('JUSTIFICADO', 'Justificado'),
    ]

    evento = models.ForeignKey(
        'agenda.EventoAgenda',
        on_delete=models.CASCADE,
        db_column='evento_id',
        related_name='presencas',
    )
    membro = models.ForeignKey(
        'contatos.Membro',
        on_delete=models.CASCADE,
        db_column='membro_id',
        related_name='presencas',
    )
    estado = models.CharField(max_length=12, choices=ESTADOS)
    justificativa = models.CharField(max_length=255, blank=True, default='')
    registrado_por = models.ForeignKey(
        'acesso.Usuario',
        on_delete=models.SET_NULL,
        db_column='registrado_por_id',
        related_name='presencas_registradas',
        null=True, blank=True,
    )
    registrado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'agenda_presencas'
        ordering = ['evento', 'membro']
        constraints = [
            models.UniqueConstraint(
                fields=['evento', 'membro'],
                name='presenca_evento_membro_unica',
            ),
        ]
        # Justificativa obrigatória quando JUSTIFICADO (CHECK).
        indexes = []

    def __str__(self):
        return f'{self.membro} @ {self.evento}: {self.estado}'
