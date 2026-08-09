"""Modelo do tema 'agendamentos' — espelha a tabela `agendamentos` do banco esferacrm."""
from django.db import models


class Agendamento(models.Model):
    contato = models.ForeignKey(
        'contatos.Contato',
        on_delete=models.CASCADE,
        db_column='contato_id',
        related_name='agendamentos',
    )
    hora = models.CharField(max_length=5)
    offset_dias = models.IntegerField(default=0)
    tipo = models.CharField(max_length=20)
    tipo_label = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'agendamentos'
        ordering = ['offset_dias', 'hora']

    def __str__(self):
        return f'{self.hora} — {self.contato_id}'
