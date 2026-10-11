"""The application must not open its former external GPRB connection."""

import pytest

from core.gprb import connection
from core.gprb.connection import _DummyConnection


def test_external_gprb_connection_is_disabled_by_default(monkeypatch):
    monkeypatch.setattr(connection._tls, 'conn', None, raising=False)
    monkeypatch.setenv('GPRB_DB_HOST', '192.0.2.50')
    monkeypatch.setenv('GPRB_DB_NAME', 'saldabritanea')
    monkeypatch.setattr(
        connection.socket,
        'create_connection',
        lambda *args, **kwargs: pytest.fail('external socket probe must not run'),
    )
    monkeypatch.setattr(
        connection.psycopg,
        'connect',
        lambda *args, **kwargs: pytest.fail('external PostgreSQL connection must not run'),
    )

    assert isinstance(connection.connect(), _DummyConnection)


def test_disabled_connector_does_not_reuse_cached_connection(monkeypatch):
    class CachedConnection:
        closed = False

        def close(self):
            self.closed = True

    cached = CachedConnection()
    monkeypatch.setattr(connection._tls, 'conn', cached, raising=False)
    monkeypatch.setattr(
        connection.psycopg,
        'connect',
        lambda *args, **kwargs: pytest.fail('external PostgreSQL connection must not run'),
    )

    assert isinstance(connection.connect(), _DummyConnection)
    assert cached.closed is True
    assert getattr(connection._tls, 'conn', None) is None


def test_gprb_test_connection_settings_require_explicit_local_target(monkeypatch):
    from teste.conftest import _gprb_test_connection_settings

    monkeypatch.setenv('GPRB_TEST_DB_HOST', 'localhost')
    monkeypatch.setenv('GPRB_TEST_DB_PORT', '5544')
    monkeypatch.setenv('GPRB_TEST_DB_USER', 'local_test_user')
    monkeypatch.setenv('GPRB_TEST_DB_PASSWORD', 'test-only-password')
    assert _gprb_test_connection_settings() == {
        'GPRB_DB_HOST': 'localhost',
        'GPRB_DB_PORT': '5544',
        'GPRB_DB_NAME': 'saldabritanea_test',
        'GPRB_DB_USER': 'local_test_user',
        'GPRB_DB_PASSWORD': 'test-only-password',
        'GPRB_DB_SSLMODE': 'disable',
        'GPRB_DB_TIMEOUT': '3',
    }


def test_gprb_test_connection_settings_rejects_remote_host(monkeypatch):
    from teste.conftest import _gprb_test_connection_settings

    monkeypatch.setenv('GPRB_TEST_DB_HOST', '192.0.2.60')
    monkeypatch.setenv('GPRB_TEST_DB_PORT', '5432')
    monkeypatch.setenv('GPRB_TEST_DB_USER', 'test')
    monkeypatch.setenv('GPRB_TEST_DB_PASSWORD', 'test-only-password')
    assert _gprb_test_connection_settings() is None


def test_gprb_test_connection_settings_skip_when_unconfigured(monkeypatch):
    from teste.conftest import _gprb_test_connection_settings

    for name in (
        'GPRB_TEST_DB_HOST', 'GPRB_TEST_DB_PORT',
        'GPRB_TEST_DB_USER', 'GPRB_TEST_DB_PASSWORD',
    ):
        monkeypatch.delenv(name, raising=False)
    assert _gprb_test_connection_settings() is None


def test_explicit_empty_gprb_password_does_not_read_project_env(monkeypatch):
    import builtins

    monkeypatch.setenv('GPRB_DB_HOST', '127.0.0.1')
    monkeypatch.setenv('GPRB_DB_PORT', '5432')
    monkeypatch.setenv('GPRB_DB_NAME', 'saldabritanea_test')
    monkeypatch.setenv('GPRB_DB_USER', 'gprbr')
    monkeypatch.setenv('GPRB_DB_PASSWORD', '')
    monkeypatch.setattr(connection.socket, 'create_connection', lambda *args, **kwargs: object())
    exists = connection.os.path.exists

    def project_env_exists(path):
        return True if str(path).endswith('.env') else exists(path)

    monkeypatch.setattr(
        connection.os.path,
        'exists',
        project_env_exists,
    )
    monkeypatch.setattr(
        builtins,
        'open',
        lambda *args, **kwargs: pytest.fail('explicit empty password must not read the project .env'),
    )
    monkeypatch.setattr(connection.psycopg, 'connect', lambda **kwargs: kwargs)

    params = connection._nova_conexao()

    assert params['host'] == '127.0.0.1'
    assert params['dbname'] == 'saldabritanea_test'
    assert params['password'] == ''
