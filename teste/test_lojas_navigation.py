"""Canonical URL contract for the Loja register and report controls."""

from types import SimpleNamespace

from django.core.paginator import Paginator
from django.http import QueryDict
from django.urls import resolve, reverse

from acesso.context_processors import _nav_itens
from contatos.paginacao import urls_paginacao


def test_lojas_navigation_uses_the_short_root_url():
    lojas = next(
        item for item in _nav_itens(url_name='index', app_atual='dashboard')
        if item['label'] == 'Lojas'
    )

    assert lojas['url'] == '/lojas/'


def test_short_lojas_routes_are_canonical_and_contatos_routes_remain_aliases():
    canonical_list = resolve('/lojas/')
    legacy_list = resolve('/contatos/lojas/')

    assert reverse('lojas') == '/lojas/'
    assert canonical_list.url_name == 'lojas'
    assert legacy_list.view_name == 'contatos:lojas'
    assert canonical_list.func is legacy_list.func
    assert reverse('lojas_exportar', kwargs={'formato': 'pdf'}) == (
        '/lojas/relatorio/pdf/'
    )
    assert reverse('contatos:lojas_exportar', kwargs={'formato': 'pdf'}) == (
        '/contatos/lojas/relatorio/pdf/'
    )


def test_numbered_pagination_elides_distant_pages_and_keeps_filters():
    page_obj = Paginator(range(1000), 20).get_page(25)
    request = SimpleNamespace(
        path='/lojas/',
        GET=QueryDict('q=Loja+filtro&page=25'),
    )

    urls = urls_paginacao(request, page_obj)

    assert [
        page.get('number', '...') for page in urls['pages']
    ] == [1, '...', 23, 24, 25, 26, 27, '...', 50]
    assert urls['pages'][4]['current'] is True
    assert urls['pages'][0]['url'] == '/lojas/?q=Loja+filtro&page=1'
