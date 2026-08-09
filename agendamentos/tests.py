"""Testes unitarios do app 'agendamentos' (Django)."""
from django.test import TestCase

from agendamentos.models import Agendamento
from contatos.models import Contato


class AgendamentoModelTest(TestCase):
    def setUp(self):
        self.contato = Contato.objects.create(nome='Ana Souza', seg='estetica')

    def test_cria_agendamento_ligado_ao_contato(self):
        agendamento = Agendamento.objects.create(
            contato=self.contato,
            hora='10:30',
            offset_dias=2,
            tipo='demo',
            tipo_label='Avaliação',
        )

        self.assertEqual(agendamento.contato_id, self.contato.id)
        self.assertEqual(agendamento.tipo_label, 'Avaliação')
        self.assertEqual(agendamento.offset_dias, 2)

    def test_excluir_contato_remove_agendamento_em_cascata(self):
        agendamento = Agendamento.objects.create(
            contato=self.contato, hora='09:00', offset_dias=0, tipo='call', tipo_label='Retorno'
        )

        self.contato.delete()

        self.assertFalse(Agendamento.objects.filter(pk=agendamento.pk).exists())
