"""The Vale register stays reachable from the primary navigation."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.test import Client
from django.urls import resolve, reverse

from acesso.context_processors import _nav_itens
from acesso.models import ROLE_ADMIN_SAAS, Tenant, Usuario
from acesso.session import iniciar_sessao
from contatos.models import Vale


def test_vale_follows_dashboard_and_uses_existing_page():
    items = _nav_itens(url_name='index', app_atual='dashboard')

    assert [item['label'] for item in items[:2]] == ['Dashboard', 'Vale']
    assert items[1]['url'] == '/vales/'


@pytest.mark.django_db
def test_root_vales_url_is_available():
    client = Client()
    response = client.get('/vales/')
    sem_barra = client.get('/vales')
    legado = client.get('/contatos/prefeituras/')

    assert response.status_code == 302
    assert sem_barra.status_code in (301, 302)
    assert sem_barra['Location'] == '/vales/'
    assert legado.status_code == 302


@pytest.mark.django_db
def test_vales_page_has_members_style_pagination_at_twenty_rows():
    suffix = uuid4().hex
    admin = Usuario.objects.create(
        nome='Admin pagination Vales',
        email=f'vales-pagination-{suffix}@example.test',
        senha='!',
        role=ROLE_ADMIN_SAAS,
        tenant=None,
    )
    for index in range(21):
        tenant = Tenant.objects.create(
            nome=f'Vale Paginação {index:02}',
            slug=f'vale-pagination-{suffix}-{index}',
        )
        Vale.objects.create(
            tenant=tenant,
            nome=f'Vale Paginação {index:02}',
            sigla=f'VP{suffix[:6]}{index:02}',
        )
    client = Client()
    session = client.session
    iniciar_sessao(SimpleNamespace(session=session), admin)
    session.save()

    response = client.get('/vales/')

    assert response.status_code == 200
    assert response.context['page_obj'].paginator.per_page == 20
    assert len(response.context['prefeituras']) == 20
    assert response.context['page_obj'].paginator.num_pages >= 2
    assert 'aria-label="Paginação"' in response.content.decode()
    assert 'aria-current="page"' in response.content.decode()
    alias = client.get('/contatos/prefeituras/')
    assert alias.context['pagination_urls']['pages'][0]['url'].startswith('/vales/')


def test_acompanhamento_replaces_financeiro_without_removing_finance_route():
    items = _nav_itens(url_name='index', app_atual='dashboard')
    labels = [item['label'] for item in items]

    assert 'Acompanhamento' in labels
    assert 'Financeiro' not in labels
    acompanhamento = next(item for item in items if item['label'] == 'Acompanhamento')
    assert acompanhamento['url'] == reverse('membros:acompanhamento')
    assert resolve(reverse('contatos:financeiro')).url_name == 'financeiro'
