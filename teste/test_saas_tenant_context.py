"""SaaS tenant selection stays separate from the user's identity tenant."""

import pytest
from django.test import Client, RequestFactory

from acesso.models import ROLE_VIEWER

SENHA = 'senha123'
SELECIONAR_TENANT_URL = '/login/tenant-contexto/'


def _cliente_logado(usuario, *, raise_request_exception=True):
    client = Client(raise_request_exception=raise_request_exception)
    response = client.post(
        '/login/', {'email': usuario.email, 'senha': SENHA},
    )
    assert response.status_code == 302
    return client


def _resolver_tenant(request):
    from acesso.tenant_context import resolve_tenant_id

    return resolve_tenant_id(request)


@pytest.mark.django_db
def test_admin_saas_selects_and_clears_tenant_context(admin_saas, tenant_aurora):
    client = _cliente_logado(admin_saas)

    selected = client.post(
        SELECIONAR_TENANT_URL,
        {'tenant_id': str(tenant_aurora.pk), 'next': '/dashboard/'},
    )

    assert selected.status_code == 302
    assert selected['Location'] == '/dashboard/'
    assert client.session['admin_tenant_id'] == tenant_aurora.pk
    assert client.session['usuario']['tenant_id'] is None
    admin_saas.refresh_from_db()
    assert admin_saas.tenant_id is None

    request = RequestFactory().get('/dashboard/')
    request.session = client.session
    assert _resolver_tenant(request) == tenant_aurora.pk

    from acesso.context_processors import web_sessao

    context = web_sessao(request)
    assert tenant_aurora.pk in {tenant.pk for tenant in context['web_tenant_options']}
    assert context['web_tenant_selected_id'] == tenant_aurora.pk
    assert context['web_tenant_selected_name'] == tenant_aurora.nome

    cleared = client.post(
        SELECIONAR_TENANT_URL,
        {'tenant_id': '', 'next': '//outside.example/path'},
    )

    assert cleared.status_code == 302
    assert cleared['Location'] == '/dashboard/'
    assert 'admin_tenant_id' not in client.session
    assert client.session['usuario']['tenant_id'] is None
    admin_saas.refresh_from_db()
    assert admin_saas.tenant_id is None


@pytest.mark.django_db
def test_selection_rejects_nonexistent_tenant(admin_saas):
    client = _cliente_logado(admin_saas)

    response = client.post(
        SELECIONAR_TENANT_URL,
        {'tenant_id': '999999999', 'next': '/dashboard/'},
    )

    assert response.status_code == 302
    assert 'admin_tenant_id' not in client.session
    admin_saas.refresh_from_db()
    assert admin_saas.tenant_id is None


@pytest.mark.django_db
def test_deleted_selected_tenant_clears_context(admin_saas, tenant_aurora):
    client = _cliente_logado(admin_saas)
    session = client.session
    session['admin_tenant_id'] = tenant_aurora.pk
    session.save()
    tenant_aurora.delete()

    request = RequestFactory().get('/dashboard/')
    request.session = client.session

    assert _resolver_tenant(request) is None
    assert 'admin_tenant_id' not in request.session


@pytest.mark.django_db
def test_non_saas_user_cannot_change_tenant_context(usuario_viewer, tenant_beta):
    client = _cliente_logado(usuario_viewer)

    response = client.post(
        SELECIONAR_TENANT_URL,
        {'tenant_id': str(tenant_beta.pk), 'next': '/dashboard/'},
    )

    assert response.status_code == 302
    assert 'admin_tenant_id' not in client.session
    assert client.session['usuario']['tenant_id'] == usuario_viewer.tenant_id
    usuario_viewer.refresh_from_db()
    assert usuario_viewer.tenant_id != tenant_beta.pk

    from acesso.context_processors import web_sessao

    request = RequestFactory().get('/dashboard/')
    request.session = client.session
    request.usuario_logado = usuario_viewer
    assert 'web_tenant_options' not in web_sessao(request)


@pytest.mark.django_db
def test_resolver_ignores_selection_for_regular_user(usuario_viewer, tenant_beta):
    request = RequestFactory().get('/dashboard/')
    request.session = {
        'usuario_id': usuario_viewer.pk,
        'usuario': {
            'role': ROLE_VIEWER,
            'tenant_id': usuario_viewer.tenant_id,
        },
        'admin_tenant_id': tenant_beta.pk,
    }
    request.usuario_logado = usuario_viewer

    assert _resolver_tenant(request) == usuario_viewer.tenant_id


@pytest.mark.django_db
def test_selection_rejects_oversized_numeric_tenant_id(admin_saas):
    client = _cliente_logado(admin_saas, raise_request_exception=False)

    response = client.post(
        SELECIONAR_TENANT_URL,
        {'tenant_id': '9' * 5000, 'next': '/dashboard/'},
    )

    assert response.status_code == 302
    assert 'admin_tenant_id' not in client.session
    admin_saas.refresh_from_db()
    assert admin_saas.tenant_id is None


@pytest.mark.django_db
def test_resolver_clears_oversized_session_tenant_id(admin_saas):
    client = _cliente_logado(admin_saas, raise_request_exception=False)
    session = client.session
    session['admin_tenant_id'] = '9' * 5000
    session.save()

    response = client.get('/dashboard/')

    assert response.status_code == 200
    assert 'admin_tenant_id' not in client.session
    assert client.session['usuario']['tenant_id'] is None
