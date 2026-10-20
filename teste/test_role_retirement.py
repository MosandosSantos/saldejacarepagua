"""Role assignment and login contracts after retiring tenant roles."""
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory

from acesso.context_processors import ROLE_LABELS
from acesso.models import (
    ROLE_VIEWER,
    ROLES,
    ROLES_ADMINISTRATIVOS,
    ROLES_ATRIB_CRIACAO,
    ROLES_DE_TENANT,
    ROLES_GESTORES_USUARIOS,
    ROLES_QUE_EDITAM,
    _ROLES_EDITAM_BASE,
    Convite,
    Usuario,
)
from acesso.views.helpers import entrar_com_usuario_gprb


@pytest.mark.django_db(transaction=True)
def test_removed_roles_are_not_assignable(client, headers_admin_saas, tenant_aurora):
    retired_roles = {'admin_company', 'operacional'}
    role_sets = (
        {role for role, _ in ROLES},
        set(ROLES_DE_TENANT),
        set(_ROLES_EDITAM_BASE),
        set(ROLES_QUE_EDITAM),
        set(ROLES_GESTORES_USUARIOS),
        set(ROLES_ATRIB_CRIACAO),
        set(ROLES_ADMINISTRATIVOS),
        set(ROLE_LABELS),
        {role for role, _ in Usuario._meta.get_field('role').choices},
        {role for role, _ in Convite._meta.get_field('papel').choices},
    )
    assert all(retired_roles.isdisjoint(roles) for roles in role_sets)
    assert ROLES_DE_TENANT == (ROLE_VIEWER,)

    for role in ('admin_company', 'operacional'):
        response = client.post(
            '/api/v1/usuarios',
            json={
                'nome': 'Retired Role',
                'email': f'retired-{role}@example.test',
                'senha': 'strong-password',
                'role': role,
                'tenant_id': tenant_aurora.pk,
            },
            headers=headers_admin_saas,
        )
        assert response.status_code == 422


@pytest.mark.django_db
def test_gprb_removed_and_unknown_roles_map_to_viewer():
    gprb_roles = ('ADMIN_LOJA', 'OPERADOR', 'MEMBER', 'UNRECOGNIZED')

    for role in gprb_roles:
        request = RequestFactory().get('/')
        request.session = SessionStore()
        user = entrar_com_usuario_gprb(
            request,
            {'email': f'{role.lower()}@example.test', 'name': role, 'role': role},
            'gprb-password',
            origem='test',
        )

        assert user.role == ROLE_VIEWER
        assert request.session['usuario']['role'] == ROLE_VIEWER


@pytest.mark.django_db(transaction=True)
def test_gprb_sys_admin_sync_remains_tenantless(tenant_aurora):
    novo_request = RequestFactory().get('/')
    novo_request.session = SessionStore()
    novo_usuario = entrar_com_usuario_gprb(
        novo_request,
        {'email': 'gprb-sys-admin-new@example.test', 'name': 'New SaaS Admin', 'role': 'SYS_ADMIN'},
        'gprb-password',
    )

    assert novo_usuario.role == 'admin_saas'
    assert novo_usuario.tenant_id is None

    existente = Usuario.objects.create(
        nome='Existing SaaS Admin',
        email='gprb-sys-admin-existing@example.test',
        senha=make_password('old-password'),
        role=ROLE_VIEWER,
        tenant=tenant_aurora,
    )
    existente_request = RequestFactory().get('/')
    existente_request.session = SessionStore()
    sincronizado = entrar_com_usuario_gprb(
        existente_request,
        {
            'email': existente.email,
            'name': 'Existing SaaS Admin',
            'role': 'SYS_ADMIN',
        },
        'gprb-password',
    )

    assert sincronizado.pk == existente.pk
    assert sincronizado.role == 'admin_saas'
    assert sincronizado.tenant_id is None


@pytest.mark.django_db(transaction=True)
def test_existing_api_token_uses_migrated_viewer_role(client, tenant_aurora):
    usuario = Usuario.objects.create(
        nome='Migrated Viewer API',
        email='migrated-viewer-api@example.test',
        senha=make_password('api-password'),
        role=ROLE_VIEWER,
        tenant=tenant_aurora,
    )
    agora = datetime.now(UTC)
    token = jwt.encode(
        {
            'sub': str(usuario.pk),
            'role': 'admin_company',
            'tenant_id': tenant_aurora.pk,
            'iss': 'gprbr',
            'iat': agora,
            'exp': agora + timedelta(days=1),
        },
        settings.JWT_SECRET,
        algorithm='HS256',
    )

    response = client.get('/api/v1/auth/me', headers={'Authorization': f'Bearer {token}'})

    assert response.status_code == 200
    assert response.json()['role'] == ROLE_VIEWER


def test_admin_company_onboarding_route_is_removed():
    from django.urls import Resolver404, resolve

    with pytest.raises(Resolver404):
        resolve('/login/onboarding/')
