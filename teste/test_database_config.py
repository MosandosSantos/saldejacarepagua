"""Runtime database selection from the supported environment variables."""

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _database_name(env_updates):
    env = os.environ.copy()
    env.pop('DATABASE_URL', None)
    env.pop('PGDATABASE', None)
    env.update({
        'DJANGO_SETTINGS_MODULE': 'core.settings',
        'DJANGO_DEBUG': '1',
        'DJANGO_SECRET_KEY': 'database-config-test-key',
        **env_updates,
    })
    result = subprocess.run(
        [
            sys.executable,
            '-c',
            'import dotenv; dotenv.load_dotenv = lambda *args, **kwargs: False; '
            'from django.conf import settings; print(settings.DATABASES["default"]["NAME"])',
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip().splitlines()[-1]


def test_default_database_name_is_saldabritanea():
    assert _database_name({}) == 'saldabritanea'


def test_database_url_override_still_wins():
    assert _database_name({
        'DATABASE_URL': 'postgresql://test:test@127.0.0.1:5432/url_override',
        'PGDATABASE': 'ignored_pg_database',
    }) == 'url_override'
