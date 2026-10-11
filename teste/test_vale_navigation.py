"""The Vale register stays reachable from the primary navigation."""

from acesso.context_processors import _nav_itens
from django.urls import reverse


def test_vale_follows_dashboard_and_uses_existing_page():
    items = _nav_itens(url_name='index', app_atual='dashboard')

    assert [item['label'] for item in items[:2]] == ['Dashboard', 'Vale']
    assert items[1]['url'] == reverse('contatos:prefeituras')
