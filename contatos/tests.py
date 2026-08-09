"""Testes unitarios do app 'contatos' (Django)."""
from django.test import TestCase

from contatos.models import Contato, Negocio


class ContatoModelTest(TestCase):
    def test_cria_contato_com_defaults(self):
        contato = Contato.objects.create(nome='Maria Lima', seg='estetica')
        Negocio.objects.create(contato=contato, titulo=contato.nome, stage='interessado', valor=0)

        self.assertEqual(contato.empresa, '—')
        self.assertEqual(contato.tel, '—')
        self.assertEqual(contato.email, '—')
        self.assertEqual(contato.procedimento, '—')
        self.assertEqual(contato.valor, 0)
        self.assertEqual(contato.stage, 'interessado')
        self.assertIsNotNone(contato.updated_at)

    def test_cria_contato_com_valor_decimal(self):
        contato = Contato.objects.create(nome='João Reis', seg='odonto')
        Negocio.objects.create(
            contato=contato, titulo=contato.nome, stage='orcamento', valor='1250.90'
        )

        self.assertEqual(float(contato.valor), 1250.90)
