import json

import pytest
from django.core.cache import cache
from django.test import RequestFactory, override_settings

from candidatos.views.api import api_lojas_por_prefeitura, api_prefeituras


class _Cursor:
    def __init__(self, one=None, all_rows=None):
        self.one = one
        self.all_rows = all_rows or []
        self.sql = []

    def execute(self, sql, params=None):
        self.sql.append((sql, params))

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.all_rows


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def close(self):
        pass


def _authed_request(path, query=None):
    request = RequestFactory().get(path, query or {})
    request.session = {'usuario_id': 1}
    return request


@pytest.mark.django_db
@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'external-tenant-cache-test',
    },
})
def test_prefeitura_cache_ignores_legacy_unscoped_entry(monkeypatch):
    cache.clear()
    legacy = [{'id': 'old-pref', 'nome': 'Vale antigo'}]
    current = [{'id': 'scg-pref', 'nome': 'Vale atual'}]
    cache.set('gprb:prefeituras', legacy, 300)
    monkeypatch.setattr('core.gprb.opcoes_prefeituras_usuario', lambda: current)

    with override_settings(GPRB_TENANT_CODE='SCG33REAA'):
        response = api_prefeituras(_authed_request('/candidato/api/prefeituras/'))

    assert response.status_code == 200
    assert json.loads(response.content)['prefeituras'] == current


@pytest.mark.django_db
@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'external-tenant-cache-test',
    },
})
def test_loja_cache_is_namespaced_by_tenant(monkeypatch):
    cache.clear()
    prefeitura_id = 'scg-pref-id'
    cache.set(f'gprb:lojas:{prefeitura_id}', [{'id': 'old-shop', 'nome': 'Loja antiga'}], 300)
    prefeitura_cursor = _Cursor(one=(prefeitura_id,))
    lojas_cursor = _Cursor(all_rows=[('scg-shop', 'Loja atual')])
    conns = iter((_Connection(prefeitura_cursor), _Connection(lojas_cursor)))
    monkeypatch.setattr('core.gprb.connect', lambda: next(conns))

    with override_settings(GPRB_TENANT_CODE='SCG33REAA'):
        response = api_lojas_por_prefeitura(
            _authed_request('/candidato/api/lojas/', {'prefeitura_id': prefeitura_id}),
        )

    assert response.status_code == 200
    assert json.loads(response.content)['lojas'] == [{'id': 'scg-shop', 'nome': 'Loja atual'}]
    assert any('SCG33REAA' in str(params) for _, params in prefeitura_cursor.sql)
    assert any('SCG33REAA' in str(params) for _, params in lojas_cursor.sql)


@pytest.mark.django_db
@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'external-tenant-cache-test',
    },
})
def test_recepcao_prefeitura_map_ignores_legacy_cache(monkeypatch):
    from recepcao.views import helpers

    cache.clear()
    monkeypatch.setattr(helpers, '_prefeituras_cache', {})
    monkeypatch.setattr(helpers, '_prefeituras_por_nome', {})
    cache.set('recepcao_prefeituras_map', {'old-pref': {'nome': 'Vale antigo', 'sigla': ''}}, 3600)
    cursor = _Cursor(all_rows=[('scg-pref', 'Vale atual', 'VA')])
    monkeypatch.setattr('core.gprb.connect', lambda: _Connection(cursor))

    with override_settings(GPRB_TENANT_CODE='SCG33REAA'):
        result = helpers.prefeituras_map()

    assert result == {'scg-pref': {'nome': 'Vale atual', 'sigla': 'VA'}}
    assert cursor.sql[0][1] == ('SCG33REAA',)


@pytest.mark.django_db
@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'external-tenant-cache-test',
    },
})
def test_kanban_prefeituras_filtro_ignores_legacy_unscoped_entry(monkeypatch):
    from recepcao.views import kanban

    cache.clear()
    legacy = [{'id': 'old-pref', 'nome': 'Vale antigo'}]
    current = [{'id': 'scg-pref', 'nome': 'Vale atual'}]
    cache.set('recepcao_prefeituras_filtro', legacy, 300)
    chamadas = []

    def _opcoes(tenant_code=None):
        chamadas.append(tenant_code)
        return current

    monkeypatch.setattr('core.gprb.opcoes_prefeituras_usuario', _opcoes)

    with override_settings(GPRB_TENANT_CODE='SCG33REAA'):
        resultado = kanban._buscar_prefeituras()

    assert resultado == current
    assert chamadas == ['SCG33REAA']
    assert cache.get('recepcao_prefeituras_filtro:SCG33REAA') == current
