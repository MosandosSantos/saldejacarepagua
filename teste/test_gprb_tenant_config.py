from django.conf import settings
from django.test import override_settings

from core.gprb import connection


def test_gprb_tenant_code_defaults_to_scg33reaa():
    assert getattr(settings, 'GPRB_TENANT_CODE', None) == 'SCG33REAA'


def test_resolve_tenant_code_uses_scg_when_setting_is_empty():
    resolver = getattr(connection, 'resolve_tenant_code', lambda explicit=None: None)
    with override_settings(GPRB_TENANT_CODE=''):
        assert resolver() == 'SCG33REAA'


def test_resolve_tenant_code_preserves_explicit_override():
    resolver = getattr(connection, 'resolve_tenant_code', lambda explicit=None: None)
    with override_settings(GPRB_TENANT_CODE='SCG33REAA'):
        assert resolver('GPRB') == 'GPRB'
