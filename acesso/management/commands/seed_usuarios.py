"""Seed idempotente de usuarios/tenant de demonstracao.

Uso: python manage.py seed_usuarios
"""
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from acesso.models import Tenant, Usuario
from funil.models import garantir_etapas


class Command(BaseCommand):
    help = 'Cria tenant e usuarios de demonstracao (idempotente).'

    def handle(self, *args, **options):
        tenant, _ = Tenant.objects.get_or_create(
            slug='clinica-aurora',
            defaults={'nome': 'Empresa Aurora (demonstração)'},
        )
        garantir_etapas(tenant.id, tenant.nicho)

        usuarios = [
            ('Admin SaaS', 'admin@esferacrm.com', 'admin_saas', None),
            ('Dona Aurora', 'dona@aurora.com', 'admin_company', tenant),
            ('Ana Souza', 'ana@aurora.com', 'operacional', tenant),
            ('Laura Leitura', 'laura@aurora.com', 'viewer', tenant),
        ]
        for nome, email, role, ten in usuarios:
            Usuario.objects.get_or_create(
                email=email,
                defaults={
                    'nome': nome,
                    'role': role,
                    'tenant': ten,
                    'senha': make_password('senha123'),
                },
            )
        self.stdout.write(self.style.SUCCESS('Seed OK — senha padrao: senha123'))
