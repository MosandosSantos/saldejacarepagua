"""Migration coverage for retiring tenant roles."""
import importlib
from datetime import timedelta

import pytest
from django.apps import apps as django_apps
from django.utils import timezone

migrar_papeis_retirados = importlib.import_module(
    'acesso.migrations.0019_retire_admin_company_operacional',
).migrar_papeis_retirados


class _SchemaEditorStub:
    """Minimal schema_editor interface used by the data migration."""

    class connection:
        alias = 'default'


@pytest.fixture
def migrated_legacy_roles():
    """Create legacy roles and run the 0019 data migration in-place.

    The old fixture migrated the whole ``acesso`` app backwards to 0018 and
    then only forward to 0019. That left the schema without columns added by
    later migrations (for example ``tenants.google_calendar_id``), so the web
    request below could not use the current middleware. Running just the data
    migration keeps the schema at HEAD and tests the same role conversion.
    """
    Tenant = django_apps.get_model('acesso', 'Tenant')
    Usuario = django_apps.get_model('acesso', 'Usuario')
    Convite = django_apps.get_model('acesso', 'Convite')

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

    migrar_papeis_retirados(django_apps, _SchemaEditorStub())

    yield {
        'Tenant': Tenant,
        'Usuario': Usuario,
        'Convite': Convite,
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


@pytest.mark.django_db
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


@pytest.mark.django_db
def test_existing_admin_saas_tenant_is_cleared(migrated_legacy_roles):
    Tenant = migrated_legacy_roles['Tenant']
    Usuario = migrated_legacy_roles['Usuario']

    tenant = Tenant.objects.get(pk=migrated_legacy_roles['tenant_id'])
    admin_saas = Usuario.objects.get(pk=migrated_legacy_roles['admin_saas_id'])

    assert tenant.dono_id == migrated_legacy_roles['owner_id']
    assert admin_saas.role == 'admin_saas'
    assert admin_saas.tenant_id is None


@pytest.mark.django_db
def test_existing_browser_session_uses_migrated_viewer_role(migrated_legacy_roles):
    from django.test import Client
    from tarefas.models import Tarefa

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
