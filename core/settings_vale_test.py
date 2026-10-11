"""Test settings using a dedicated disposable local PostgreSQL database."""

from copy import deepcopy

from core import settings as base_settings


for _setting_name in dir(base_settings):
    if _setting_name.isupper():
        globals()[_setting_name] = getattr(base_settings, _setting_name)

DATABASES = deepcopy(base_settings.DATABASES)
DATABASES['default'].setdefault('TEST', {})['NAME'] = 'test_saldabritanea_vales'
GPRB_DB_ENABLED = False
