from uuid import uuid4

import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client
from django.urls import resolve, reverse

from acesso.models import Usuario


def _web_client(usuario):
    client = Client()
    session = client.session
    session['usuario_id'] = usuario.id
    session['usuario'] = {
        'nome': usuario.nome,
        'email': usuario.email,
        'role': usuario.role,
        'tenant_id': usuario.tenant_id,
    }
    session['nicho'] = 'saude'
    session.save()
    return client


def _navigation_admin():
    return Usuario.objects.create(
        nome='Admin Navegação',
        email=f'admin-nav-{uuid4().hex}@example.test',
        role='admin_saas',
        tenant=None,
        senha=make_password('test-password'),
    )


def test_reverse_kanban_uses_iniciacao():
    assert reverse('recepcao:kanban') == '/iniciacao/'


def test_old_and_new_root_paths_reach_kanban():
    assert resolve('/iniciacao/').func is resolve('/recepcao/').func
    assert reverse('recepcao_legacy:kanban') == '/recepcao/'


def test_legacy_mover_path_preserves_post_route():
    canonical = reverse('recepcao:mover', args=(42,))
    legacy = reverse('recepcao_legacy:mover', args=(42,))
    assert canonical == '/iniciacao/42/mover/'
    assert legacy == '/recepcao/42/mover/'
    assert resolve(canonical).func is resolve(legacy).func


@pytest.mark.django_db
def test_kanban_shows_iniciacao_branding():
    response = _web_client(_navigation_admin()).get('/iniciacao/')
    html = response.content.decode('utf-8')

    assert response.status_code == 200
    assert 'Flow de Iniciação' in html
    assert 'Iniciação' in html


@pytest.mark.django_db
def test_kanban_ajax_urls_use_iniciacao_prefix():
    html = _web_client(_navigation_admin()).get('/iniciacao/').content.decode('utf-8')

    assert html.count("fetch('/iniciacao/'") == 2
    assert "url = '/iniciacao/'" in html
