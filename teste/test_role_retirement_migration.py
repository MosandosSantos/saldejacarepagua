"""Migration coverage for retiring tenant roles."""
from datetime import timedelta

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client
from django.utils import timezone
from tarefas.models import Tarefa


@pytest.fixture
def migrated_legacy_roles():
    migration_from = [('acesso', '0018_usuario_loja_id')]
    migration_to = [('acesso', '0019_retire_admin_company_operacional')]
    executor = MigrationExecutor(connection)

    try:
        executor.migrate(migration_from)
        old_apps = executor.loader.project_state(migration_from).apps
        Tenant = old_apps.get_model('acesso', 'Tenant')
        Usuario = old_apps.get_model('acesso', 'Usuario')
        Convite = old_apps.get_model('acesso', 'Convite')

        tenant = Tenant.objects.create(nome='Migration tenant', slug='role-retirement-migration')
        admin = Usuario.objects.create(
            nome='Tenant Owner',
            email='migration-admin-company@example.test',
            senha='legacy-hash',
            role='admin_company',
            tenant_id=tenant.pk,
        )
        operacional = Usuario.objects.create(
            nome='Tenant Operator',
            email='migration-operacional@example.test',
            senha='legacy-hash',
            role='operacional',
            tenant_id=tenant.pk,
        )
        admin_saas = Usuario.objects.create(
            nome='Legacy SaaS Admin',
            email='migration-admin-saas@example.test',
            senha='legacy-hash',
            role='admin_saas',
            tenant_id=tenant.pk,
        )
        Tenant.objects.filter(pk=tenant.pk).update(dono_id=admin.pk)

        expiracao = timezone.now() + timedelta(days=3)
        convite_admin = Convite.objects.create(
            token='migration-admin-company-token',
            tenant_id=tenant.pk,
            email='invite-admin-company@example.test',
            papel='admin_company',
            expira_em=expiracao,
        )
        convite_operacional = Convite.objects.create(
            token='migration-operacional-token',
            tenant_id=tenant.pk,
            email='invite-operacional@example.test',
            papel='operacional',
            expira_em=expiracao,
        )

        executor = MigrationExecutor(connection)
        executor.migrate(migration_to)
        new_apps = executor.loader.project_state(migration_to).apps
        yield {
            'Tenant': new_apps.get_model('acesso', 'Tenant'),
            'Usuario': new_apps.get_model('acesso', 'Usuario'),
            'Convite': new_apps.get_model('acesso', 'Convite'),
            'tenant_id': tenant.pk,
            'owner_id': admin.pk,
            'users': {
                admin.pk: ('Tenant Owner', 'migration-admin-company@example.test', 'viewer', tenant.pk),
                operacional.pk: ('Tenant Operator', 'migration-operacional@example.test', 'viewer', tenant.pk),
                admin_saas.pk: ('Legacy SaaS Admin', 'migration-admin-saas@example.test', 'admin_saas', None),
            },
            'invites': {
                convite_admin.pk: ('migration-admin-company-token', 'invite-admin-company@example.test'),
                convite_operacional.pk: ('migration-operacional-token', 'invite-operacional@example.test'),
            },
            'admin_saas_id': admin_saas.pk,
            'operacional_id': operacional.pk,
        }
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())


@pytest.mark.django_db(transaction=True)
def test_migration_converts_retired_users_and_pending_invites_to_viewer(migrated_legacy_roles):
    Tenant = migrated_legacy_roles['Tenant']
    Usuario = migrated_legacy_roles['Usuario']
    Convite = migrated_legacy_roles['Convite']
    tenant_id = migrated_legacy_roles['tenant_id']

    tenant = Tenant.objects.get(pk=tenant_id)
    assert tenant.dono_id == migrated_legacy_roles['owner_id']

    for user_id, (nome, email, role, expected_tenant_id) in migrated_legacy_roles['users'].items():
        user = Usuario.objects.get(pk=user_id)
        assert (user.nome, user.email, user.role, user.tenant_id) == (
            nome, email, role, expected_tenant_id,
        )

    for invite_id, (token, email) in migrated_legacy_roles['invites'].items():
        invite = Convite.objects.get(pk=invite_id)
        assert (invite.token, invite.email, invite.tenant_id, invite.papel) == (
            token, email, tenant_id, 'viewer',
        )
        assert invite.usado_em is None
        assert invite.cancelado_em is None


@pytest.mark.django_db(transaction=True)
def test_existing_admin_saas_tenant_is_cleared(migrated_legacy_roles):
    Tenant = migrated_legacy_roles['Tenant']
    Usuario = migrated_legacy_roles['Usuario']

    tenant = Tenant.objects.get(pk=migrated_legacy_roles['tenant_id'])
    admin_saas = Usuario.objects.get(pk=migrated_legacy_roles['admin_saas_id'])

    assert tenant.dono_id == migrated_legacy_roles['owner_id']
    assert admin_saas.role == 'admin_saas'
    assert admin_saas.tenant_id is None


@pytest.mark.django_db(transaction=True)
def test_existing_browser_session_uses_migrated_viewer_role(migrated_legacy_roles):
    Usuario = migrated_legacy_roles['Usuario']
    usuario = Usuario.objects.get(pk=migrated_legacy_roles['operacional_id'])
    assert usuario.role == 'viewer'

    client = Client()
    session = client.session
    session['usuario_id'] = usuario.pk
    session['usuario'] = {
        'id': usuario.pk,
        'nome': usuario.nome,
        'email': usuario.email,
        'role': 'operacional',
        'tenant_id': usuario.tenant_id,
    }
    session['nicho'] = ''
    session.save()

    response = client.post('/recepcao/nova-atividade/', {
        'titulo': 'Must not be created from migrated viewer session',
        'prioridade': 'media',
    })

    assert response.status_code == 302
    assert response.url == '/dashboard/'
    assert client.session['usuario_id'] == usuario.pk
    assert client.session['usuario']['role'] == 'viewer'
    assert not Tarefa.objects.filter(
        titulo='Must not be created from migrated viewer session',
    ).exists()
