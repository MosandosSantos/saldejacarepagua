"""Isolated Vale test settings; require an explicit Docker database URL."""

import os
from copy import deepcopy
from urllib.parse import urlsplit

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from core import settings as base_settings


for _setting_name in dir(base_settings):
    if _setting_name.isupper():
        globals()[_setting_name] = getattr(base_settings, _setting_name)

_database_url = os.environ.get('VALE_TEST_DATABASE_URL', '').strip()
if not _database_url:
    raise ImproperlyConfigured(
        'Set VALE_TEST_DATABASE_URL to the local Docker PostgreSQL URL; '
        'the default host database is intentionally not used by Vale tests.'
    )

_parsed_database_url = urlsplit(_database_url)
_docker_target = (
    _parsed_database_url.username == 'gprbr'
    and _parsed_database_url.hostname in ('localhost', '127.0.0.1', 'db')
    and _parsed_database_url.path == '/saldabritanea'
)
_ci_target = (
    _parsed_database_url.username == 'postgres'
    and _parsed_database_url.hostname in ('localhost', '127.0.0.1')
    and _parsed_database_url.path == '/gprbr_test'
)
if _parsed_database_url.scheme not in ('postgres', 'postgresql') or not (
    _docker_target or _ci_target
):
    raise ImproperlyConfigured(
        'VALE_TEST_DATABASE_URL must target Docker saldabritanea as gprbr, '
        'or the isolated CI database gprbr_test as postgres.'
    )

DATABASES = deepcopy(base_settings.DATABASES)
DATABASES['default'] = dj_database_url.parse(_database_url, conn_max_age=0)
DATABASES['default'].setdefault('TEST', {})['NAME'] = 'test_saldabritanea_vales'
GPRB_DB_ENABLED = False
