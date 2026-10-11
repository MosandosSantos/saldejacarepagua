"""Persistence tests for the local, tenant-scoped Vale registry."""

import os
import subprocess
import sys
from configparser import ConfigParser
from datetime import date
from decimal import Decimal
from uuid import uuid4
from pathlib import Path

import pytest


def test_vale_test_settings_require_explicit_database_url():
    env = os.environ.copy()
    env.pop('VALE_TEST_DATABASE_URL', None)

    result = subprocess.run(
        [sys.executable, '-c', 'import django; django.setup()'],
        env={**env, 'DJANGO_SETTINGS_MODULE': 'core.settings_vale_test'},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert 'VALE_TEST_DATABASE_URL' in result.stderr


def test_vale_test_settings_reject_external_database_url():
    env = os.environ.copy()
    env.update({
        'DJANGO_SETTINGS_MODULE': 'core.settings_vale_test',
        'VALE_TEST_DATABASE_URL': 'postgresql://user:pass@external.example:5432/saldabritanea',
    })

    result = subprocess.run(
        [sys.executable, '-c', 'import django; django.setup()'],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert 'must target Docker saldabritanea' in result.stderr


def test_vale_test_settings_accept_isolated_ci_database_url():
    env = os.environ.copy()
    env.update({
        'DJANGO_SETTINGS_MODULE': 'core.settings_vale_test',
        'VALE_TEST_DATABASE_URL': 'postgresql://postgres:postgres@localhost:5432/gprbr_test',
    })

    result = subprocess.run(
        [
            sys.executable,
            '-c',
            'import django; django.setup(); from django.conf import settings; '
            'assert settings.DATABASES["default"]["TEST"]["NAME"] == '
            '"test_saldabritanea_vales"',
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_pytest_defaults_to_fail_closed_database_settings():
    config = ConfigParser()
    config.read(Path(__file__).resolve().parents[1] / 'pytest.ini')

    assert config['pytest']['DJANGO_SETTINGS_MODULE'] == 'core.settings_vale_test'


def test_vale_views_import_without_uncommitted_tenant_decorator():
    script = r'''
import os
import importlib.util
import sys
import types
from pathlib import Path

os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'
import django
django.setup()

decorators = types.ModuleType('acesso.decorators')
def passthrough(view):
    return view
decorators.filtro_tenant = lambda request, queryset: queryset
decorators.tenant_id_da_sessao = lambda request: None
decorators.web_login_required = passthrough
decorators.web_requer_edicao = passthrough
sys.modules['acesso.decorators'] = decorators

views_package = types.ModuleType('contatos.views')
views_package.__path__ = []
sys.modules['contatos.views'] = views_package
spec = importlib.util.spec_from_file_location(
    'contatos.views.vales', Path('contatos/views/vales.py'),
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
'''
    result = subprocess.run(
        [sys.executable, '-c', script],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_vale_model_is_registered():
    from contatos.models import Vale

    assert Vale._meta.db_table == 'vales'


def test_vale_uses_local_table_and_tenant_fk():
    from acesso.models import Tenant
    from contatos.models import Vale

    field = Vale._meta.get_field('tenant')

    assert field.related_model is Tenant
    assert field.column == 'tenant_id'
    assert field.null is False
    assert Vale._meta.ordering == ['nome']


@pytest.mark.django_db
def test_vale_contact_fields_round_trip():
    from acesso.models import Tenant
    from contatos.models import Vale

    tenant = Tenant.objects.create(
        nome='Vale de teste', slug=f'vale-{uuid4().hex}',
    )
    vale = Vale.objects.create(
        tenant=tenant,
        nome='Vale Centro',
        sigla='VC',
        prefeito='Delegado Teste',
        telefone='(21) 90000-0000',
        email='delegado@gprbr',
        secretario_nome='Secretário Teste',
        secretario_email='farelli@gprbr',
        secretario_telefone='(21) 99999-9999',
        tesoureiro_nome='Tesoureiro Teste',
        tesoureiro_email='tesouraria@potencia.com',
        tesoureiro_telefone='(21) 98888-9999',
        pix='pix-vale-centro',
        valor_anuidade=Decimal('1500.00'),
        vencimento_anuidade=date(2027, 1, 31),
    )

    saved = Vale.objects.get(pk=vale.pk, tenant=tenant)

    assert saved.secretario_nome == 'Secretário Teste'
    assert saved.secretario_email == 'farelli@gprbr'
    assert saved.secretario_telefone == '(21) 99999-9999'
    assert saved.tesoureiro_nome == 'Tesoureiro Teste'
    assert saved.tesoureiro_email == 'tesouraria@potencia.com'
    assert saved.tesoureiro_telefone == '(21) 98888-9999'
    assert saved.valor_anuidade == Decimal('1500.00')
    assert saved.vencimento_anuidade == date(2027, 1, 31)


@pytest.mark.django_db
def test_vale_preserves_blank_local_contacts():
    from acesso.models import Tenant
    from contatos.models import Vale

    tenant = Tenant.objects.create(
        nome='Vale sem contatos', slug=f'vale-{uuid4().hex}',
    )
    vale = Vale.objects.create(tenant=tenant, nome='Vale sem contatos')

    assert vale.secretario_nome == ''
    assert vale.secretario_email == ''
    assert vale.secretario_telefone == ''
    assert vale.tesoureiro_nome == ''
    assert vale.tesoureiro_email == ''
    assert vale.tesoureiro_telefone == ''
    assert vale.valor_anuidade is None
    assert vale.vencimento_anuidade is None
