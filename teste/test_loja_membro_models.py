"""Model contracts for tenant-local Lojas, Membros, and Loja PDFs."""

from uuid import uuid4

import pytest
from django.apps import apps
from django.db import IntegrityError, transaction

from acesso.models import Tenant
from contatos.models import Loja, LojaPdf

pytestmark = pytest.mark.django_db(transaction=True)


def _registered_model(name):
    return apps.all_models.get('contatos', {}).get(name.lower())


def _local_models_or_skip():
    loja = _registered_model('Loja')
    membro = _registered_model('Membro')
    if loja is None or membro is None:
        pytest.skip('Os modelos locais de Loja e Membro ainda não foram registrados.')
    return loja, membro


def _tenant(label):
    suffix = uuid4().hex
    return Tenant.objects.create(nome=label, slug=f'{label.lower()}-{suffix}')


def test_local_loja_and_membro_models_are_registered():
    assert _registered_model('Loja') is not None
    assert _registered_model('Membro') is not None


def test_local_models_use_tenant_and_expected_tables():
    Loja, Membro = _local_models_or_skip()

    assert Loja._meta.db_table == 'lojas'
    assert Membro._meta.db_table == 'membros'
    assert Loja._meta.get_field('tenant').remote_field.model is Tenant
    assert Membro._meta.get_field('tenant').remote_field.model is Tenant


def test_loja_president_is_a_local_member_relation():
    Loja, Membro = _local_models_or_skip()
    tenant = _tenant('presidente')
    membro = Membro.objects.create(tenant=tenant, nome='Presidente local')

    loja = Loja.objects.create(
        tenant=tenant,
        nome='Loja com presidente',
        deputado_mestre=membro,
    )

    assert loja.deputado_mestre_id == membro.pk
    assert Loja._meta.get_field('deputado_mestre').remote_field.model is Membro


def test_membro_cpf_is_unique_per_tenant_only():
    _, Membro = _local_models_or_skip()
    first_tenant = _tenant('cpf-a')
    second_tenant = _tenant('cpf-b')
    Membro.objects.create(tenant=first_tenant, nome='Membro A', cpf='12345678901')
    Membro.objects.create(tenant=second_tenant, nome='Membro B', cpf='12345678901')

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Membro.objects.create(
                tenant=first_tenant,
                nome='Membro duplicado',
                cpf='12345678901',
            )


def test_membro_can_have_zero_or_multiple_lojas_from_same_tenant():
    Loja, Membro = _local_models_or_skip()
    tenant = _tenant('membro-lojas')
    membro = Membro.objects.create(tenant=tenant, nome='Membro sem loja')
    primeira = Loja.objects.create(tenant=tenant, nome='Loja A')
    segunda = Loja.objects.create(tenant=tenant, nome='Loja B')

    assert membro.lojas.count() == 0
    membro.lojas.add(primeira, segunda)

    assert set(membro.lojas.values_list('pk', flat=True)) == {primeira.pk, segunda.pk}


def test_loja_pdf_is_one_to_one_with_local_loja():
    Loja, _ = _local_models_or_skip()
    tenant = _tenant('loja-pdf')
    loja = Loja.objects.create(tenant=tenant, nome='Loja com PDF')
    pdf_field = LojaPdf._meta.get_field('loja')
    assert pdf_field.one_to_one
    assert not pdf_field.null
    LojaPdf.objects.create(loja=loja, arquivo='lojas/valores/tabela.pdf')

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            LojaPdf.objects.create(loja=loja, arquivo='lojas/valores/outra.pdf')

    assert LojaPdf.objects.filter(loja=loja).count() == 1


def test_loja_pdf_cannot_exist_without_local_loja():
    _local_models_or_skip()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            LojaPdf.objects.create(loja=None, arquivo='lojas/valores/orphan.pdf')


def test_loja_corpo_choices_and_default_to_perfeicao():
    assert Loja.CORPO_CHOICES == (
        ('perfeicao', 'Perfeição'),
        ('capitulo', 'Capítulo'),
        ('kadosh', 'Kadosh'),
        ('consistorio', 'Consistório'),
        ('sc33', 'SC33'),
    )

    tenant = _tenant('loja-corpo-default')
    loja = Loja.objects.create(tenant=tenant, nome='Loja default')

    assert loja.corpo == 'perfeicao'
