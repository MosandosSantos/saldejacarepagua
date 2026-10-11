"""Persistence tests for the local, tenant-scoped Vale registry."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest


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
