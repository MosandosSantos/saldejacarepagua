"""Seed idempotente de usuarios/tenant de demonstracao.

Uso: python manage.py seed_usuarios

Gera senhas aleatorias seguras para cada usuario. A senha de cada usuario
é impressa no terminal e salva em .env-seed para referencia.
"""
import secrets

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from acesso.models import Tenant, Usuario
from recepcao.models import garantir_etapas


class Command(BaseCommand):
    help = 'Cria tenant e usuarios de demonstracao (idempotente).'

    def handle(self, *args, **options):
        tenant, _ = Tenant.objects.get_or_create(
            slug='loja-virtual',
            defaults={'nome': 'Loja Virtual (demonstração)', 'nicho': 'ecommerce'},
        )
        garantir_etapas(tenant.id, tenant.nicho)

        usuarios = [
            ('Admin SaaS', 'admin@gprbr.com', 'admin_saas', None),
            ('Carlos Silva', 'carlos@lojavirtual.com', 'admin_company', tenant),
            ('Ana Souza', 'ana@lojavirtual.com', 'operacional', tenant),
            ('Pedro Costa', 'pedro@lojavirtual.com', 'viewer', tenant),
        ]
        credenciais = []
        for nome, email, role, ten in usuarios:
            _, created = Usuario.objects.get_or_create(
                email=email,
                defaults={
                    'nome': nome,
                    'role': role,
                    'tenant': ten,
                },
            )
            if created:
                senha = secrets.token_urlsafe(12)
                created_obj = Usuario.objects.get(email=email)
                created_obj.senha = make_password(senha)
                created_obj.save(update_fields=['senha'])
                credenciais.append((email, senha))

        if credenciais:
            self.stdout.write(self.style.SUCCESS('Seed OK — credenciais geradas:'))
            for email, senha in credenciais:
                self.stdout.write(f'  {email} → {senha}')
            # Salvar em arquivo para referencia
            with open('.env-seed', 'w') as f:
                f.write('# Credenciais geradas pelo seed_usuarios\n')
                for email, senha in credenciais:
                    f.write(f'# {email} → {senha}\n')
            self.stdout.write(self.style.WARNING('Credenciais salvas em .env-seed'))
        else:
            self.stdout.write(self.style.WARNING('Seed OK — usuarios ja existentes, nenhuma senha gerada.'))
