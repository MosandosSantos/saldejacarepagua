import importlib
import importlib.util
import json
from urllib.parse import parse_qs

import pytest
from django.conf import settings
from django.test import override_settings
from urllib.error import URLError

from core import settings as core_settings


def _turnstile_module():
    if importlib.util.find_spec('acesso.turnstile') is None:
        pytest.fail('acesso.turnstile is not implemented yet')
    return importlib.import_module('acesso.turnstile')


class _SiteverifyResponse:
    def __init__(self, result):
        self.body = json.dumps(result).encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, *_args):
        return self.body


def test_turnstile_debug_fallback_uses_official_test_keys():
    resolver = getattr(core_settings, 'resolve_turnstile_keys', lambda *args: None)
    assert resolver(True, '', '') == (
        '1x00000000000000000000AA',
        '1x0000000000000000000000000000000AA',
    )


def test_turnstile_production_requires_real_keys():
    resolver = getattr(core_settings, 'resolve_turnstile_keys', lambda *args: None)
    assert resolver(False, '', '') == ('', '')
    assert resolver(False, 'real-site-key', 'real-secret-key') == (
        'real-site-key', 'real-secret-key',
    )
    assert resolver(
        False,
        '1x00000000000000000000AA',
        '1x0000000000000000000000000000000AA',
    ) == ('', '')


def test_turnstile_rejects_empty_token_without_network(monkeypatch):
    module = _turnstile_module()
    monkeypatch.setattr(module, 'urlopen', lambda *args, **kwargs: pytest.fail('unexpected network'))
    with override_settings(
        CLOUDFLARE_TURNSTILE_CONFIGURED=True,
        CLOUDFLARE_TURNSTILE_SECRET_KEY='test-secret',
    ):
        assert module.verify_turnstile_token('') is False


def test_turnstile_rejects_oversized_token_without_network(monkeypatch):
    module = _turnstile_module()
    monkeypatch.setattr(module, 'urlopen', lambda *args, **kwargs: pytest.fail('unexpected network'))
    with override_settings(
        CLOUDFLARE_TURNSTILE_CONFIGURED=True,
        CLOUDFLARE_TURNSTILE_SECRET_KEY='test-secret',
    ):
        assert module.verify_turnstile_token('x' * (module.MAX_TOKEN_LENGTH + 1)) is False


def test_turnstile_validates_siteverify_success(monkeypatch):
    module = _turnstile_module()
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return _SiteverifyResponse({'success': True})

    monkeypatch.setattr(module, 'urlopen', fake_urlopen)
    with override_settings(
        CLOUDFLARE_TURNSTILE_CONFIGURED=True,
        CLOUDFLARE_TURNSTILE_SECRET_KEY='test-secret',
    ):
        assert module.verify_turnstile_token('test-token') is True

    request, timeout = requests[0]
    assert request.full_url == 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
    assert parse_qs(request.data.decode('utf-8')) == {
        'secret': ['test-secret'], 'response': ['test-token'],
    }
    assert timeout <= 5


def test_turnstile_rejects_failed_siteverify(monkeypatch):
    module = _turnstile_module()
    monkeypatch.setattr(module, 'urlopen', lambda *args, **kwargs: _SiteverifyResponse({'success': False}))
    with override_settings(
        CLOUDFLARE_TURNSTILE_CONFIGURED=True,
        CLOUDFLARE_TURNSTILE_SECRET_KEY='test-secret',
    ):
        assert module.verify_turnstile_token('invalid-token') is False


def test_turnstile_fails_closed_on_network_error(monkeypatch):
    module = _turnstile_module()
    monkeypatch.setattr(module, 'urlopen', lambda *args, **kwargs: (_ for _ in ()).throw(URLError('offline')))
    with override_settings(
        CLOUDFLARE_TURNSTILE_CONFIGURED=True,
        CLOUDFLARE_TURNSTILE_SECRET_KEY='test-secret',
    ):
        assert module.verify_turnstile_token('test-token') is False


def test_turnstile_requires_keys():
    module = _turnstile_module()
    with override_settings(
        CLOUDFLARE_TURNSTILE_CONFIGURED=False,
        CLOUDFLARE_TURNSTILE_SECRET_KEY='',
    ):
        assert module.verify_turnstile_token('test-token') is False


def test_turnstile_csp_allows_cloudflare_widget_and_siteverify():
    assert 'https://challenges.cloudflare.com' in settings.CSP_DIRETIVAS['script-src']
    assert 'https://challenges.cloudflare.com' in settings.CSP_DIRETIVAS['frame-src']
    assert 'https://challenges.cloudflare.com' in settings.CSP_DIRETIVAS['connect-src']
