"""Testes do campo `hora` em Tarefa — consolidação da Agenda em Tarefas.

Cobre: criar tarefa com hora válida, ordenação por hora no mesmo vencimento,
rejeição de hora inválida e hora opcional.
"""

from datetime import date, time, timedelta

from django.test import TestCase

from acesso.models import Tenant, Usuario
from tarefas.models import Tarefa


def _fazer_login(client, usuario):
    s = client.session
    s['usuario_id'] = usuario.id
    s['usuario'] = {'nome': usuario.nome, 'email': usuario.email, 'role': usuario.role,
                    'tenant_id': usuario.tenant_id}
    s['nicho'] = 'saude'
    s.save()


class HoraTarefaTest(TestCase):
    """Testes web do campo hora (criar/editar pela lista e pela ficha)."""

    def setUp(self):
        from django.contrib.auth.hashers import make_password

        self.tenant = Tenant.objects.create(nome='Clínica Aurora', slug='clinica-aurora')
        self.admin = Usuario.objects.create(
            nome='Dona Aurora', email='dona@aurora.com', role='admin_company',
            tenant=self.tenant, senha=make_password('senha123'),
        )
        _fazer_login(self.client, self.admin)

    def test_cria_tarefa_com_hora_valida(self):
        resp = self.client.post('/tarefas/', {
            'acao': 'criar', 'titulo': 'Confirmar avaliação', 'hora': '09:30',
        })
        self.assertEqual(resp.status_code, 302)
        t = Tarefa.objects.get(titulo='Confirmar avaliação')
        self.assertEqual(t.hora, time(9, 30))

    def test_hora_aparece_na_lista(self):
        Tarefa.objects.create(tenant=self.tenant, titulo='Ligar', hora=time(14, 15))
        html = self.client.get('/tarefas/').content.decode('utf-8')
        self.assertIn('14:15', html)

    def test_edita_hora(self):
        t = Tarefa.objects.create(tenant=self.tenant, titulo='Ligar', hora=time(8, 0))
        resp = self.client.post(f'/tarefas/{t.id}/editar/', {
            'titulo': 'Ligar', 'hora': '17:45',
        })
        self.assertEqual(resp.status_code, 302)
        t.refresh_from_db()
        self.assertEqual(t.hora, time(17, 45))

    def test_rejeita_hora_invalida(self):
        resp = self.client.post('/tarefas/', {
            'acao': 'criar', 'titulo': 'X', 'hora': '25:99',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertIn('hora válida'.encode(), resp.content)
        self.assertEqual(Tarefa.objects.count(), 0)

    def test_cria_tarefa_sem_hora(self):
        resp = self.client.post('/tarefas/', {'acao': 'criar', 'titulo': 'Sem hora'})
        self.assertEqual(resp.status_code, 302)
        t = Tarefa.objects.get(titulo='Sem hora')
        self.assertIsNone(t.hora)


class HoraTarefaOrdenacaoTest(TestCase):
    """Hora opcional + ordenação por hora dentro do mesmo vencimento."""

    def test_hora_opcional_e_nula(self):
        t = Tarefa.objects.create(tenant=Tenant.objects.create(nome='Beta', slug='beta'), titulo='X')
        self.assertIsNone(t.hora)

    def test_ordena_por_hora_no_mesmo_vencimento(self):
        tenant = Tenant.objects.create(nome='Aurora', slug='aurora-ord')
        venc = date.today() + timedelta(days=1)
        Tarefa.objects.create(tenant=tenant, titulo='Tarde', vencimento=venc, hora=time(16, 0))
        Tarefa.objects.create(tenant=tenant, titulo='Manhã', vencimento=venc, hora=time(8, 30))
        Tarefa.objects.create(tenant=tenant, titulo='Meio', vencimento=venc, hora=time(12, 0))
        ordem = list(Tarefa.objects.filter(vencimento=venc).values_list('titulo', flat=True))
        self.assertEqual(ordem, ['Manhã', 'Meio', 'Tarde'])
