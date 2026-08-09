"""Testes unitarios do app 'acesso' (Django)."""
from django.contrib.auth.hashers import check_password, make_password
from django.test import TestCase

from acesso.models import ROLE_ADMIN_SAAS, Tenant, Usuario


class TenantModelTest(TestCase):
    def test_cria_tenant(self):
        tenant = Tenant.objects.create(nome='Clínica Teste', slug='clinica-teste')

        self.assertEqual(tenant.slug, 'clinica-teste')
        self.assertIsNotNone(tenant.created_at)


class UsuarioModelTest(TestCase):
    def test_cria_usuario_com_senha_hasheada(self):
        tenant = Tenant.objects.create(nome='Clínica Teste', slug='clinica-teste')
        usuario = Usuario.objects.create(
            nome='Ana Souza',
            email='ana@aurora.com',
            senha=make_password('senha123'),
            role='operacional',
            tenant=tenant,
        )

        self.assertNotEqual(usuario.senha, 'senha123')
        self.assertTrue(check_password('senha123', usuario.senha))
        self.assertEqual(usuario.role, 'operacional')

    def test_admin_saas_sem_tenant(self):
        usuario = Usuario.objects.create(
            nome='Plataforma',
            email='admin@saas.com',
            senha=make_password('senha123'),
            role=ROLE_ADMIN_SAAS,
            tenant=None,
        )

        self.assertIsNone(usuario.tenant)
