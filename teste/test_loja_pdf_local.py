"""PDF attachment CRUD for local tenant-scoped Lojas."""

from uuid import uuid4

import pytest
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from acesso.models import ROLE_ADM, ROLE_DELEGADO, Tenant, Usuario
from contatos.models import Loja, LojaPdf, Vale


pytestmark = pytest.mark.django_db(transaction=True)

PDF_BYTES = b'%PDF-1.4\nlocal values\n%%EOF'


@pytest.fixture(autouse=True)
def gprb_must_not_be_used(monkeypatch):
    from repositories import gprb_repository

    monkeypatch.setattr(
        gprb_repository,
        'connect',
        lambda: pytest.fail('local Loja PDF views must not connect to GPRB'),
    )


@pytest.fixture
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def _tenant_vale(sigla):
    suffix = uuid4().hex
    tenant = Tenant.objects.create(nome=sigla, slug=f'{sigla.lower()}-{suffix}')
    Vale.objects.create(tenant=tenant, nome=f'Vale {sigla}', sigla=sigla)
    return tenant


def _client(tenant, role=ROLE_DELEGADO):
    suffix = uuid4().hex
    user = Usuario.objects.create(
        nome='Editor PDF',
        email=f'pdf-{suffix}@example.test',
        senha=make_password('senha-de-teste'),
        role=role,
        tenant=tenant,
    )
    client = Client()
    session = client.session
    session['usuario_id'] = user.pk
    session['usuario'] = {
        'nome': user.nome,
        'email': user.email,
        'role': user.role,
        'tenant_id': tenant.pk,
    }
    session.save()
    return client


def _pdf_upload(name='valores.pdf', content=PDF_BYTES):
    return SimpleUploadedFile(name, content, content_type='application/pdf')


def test_upload_replace_and_remove_pdf_for_local_loja(media_root):
    tenant = _tenant_vale('PDA')
    loja = Loja.objects.create(tenant=tenant, nome='Loja PDF')
    client = _client(tenant)

    uploaded = client.post(
        f'/contatos/loja/{loja.pk}/pdf/',
        {'pdf': _pdf_upload()},
    )

    assert uploaded.status_code == 302
    pdf = LojaPdf.objects.get(loja=loja)
    first_path = media_root / pdf.arquivo.name
    assert first_path.exists()
    assert b'local values' in first_path.read_bytes()

    replaced = client.post(
        f'/contatos/loja/{loja.pk}/pdf/',
        {'pdf': _pdf_upload('novo.pdf', b'%PDF-1.7\nnew values\n%%EOF')},
    )

    assert replaced.status_code == 302
    pdf.refresh_from_db()
    assert LojaPdf.objects.filter(loja=loja).count() == 1
    assert not first_path.exists()

    removed = client.post(f'/contatos/loja/{loja.pk}/pdf/remover/')

    assert removed.status_code == 302
    assert not LojaPdf.objects.filter(loja=loja).exists()
    assert not (media_root / pdf.arquivo.name).exists()


@pytest.mark.parametrize(
    ('name', 'content', 'expected_error'),
    [
        ('valores.txt', b'%PDF-1.4\n', 'invalido'),
        ('fake.pdf', b'not a pdf', 'invalido'),
        ('grande.pdf', b'%PDF-' + b'x' * (10 * 1024 * 1024 + 1), 'tamanho'),
    ],
)
def test_upload_rejects_invalid_or_oversized_pdf(media_root, name, content, expected_error):
    tenant = _tenant_vale('PDB')
    loja = Loja.objects.create(tenant=tenant, nome='Loja PDF inválido')
    client = _client(tenant)

    response = client.post(
        f'/contatos/loja/{loja.pk}/pdf/',
        {'pdf': _pdf_upload(name, content)},
    )

    assert response.status_code == 302
    assert f'erro={expected_error}' in response['Location']
    assert not LojaPdf.objects.filter(loja=loja).exists()


def test_other_tenant_cannot_upload_or_remove_pdf_for_loja(media_root):
    tenant_a = _tenant_vale('PDC')
    tenant_b = _tenant_vale('PDD')
    loja = Loja.objects.create(tenant=tenant_b, nome='Loja privada')
    client = _client(tenant_a)

    upload = client.post(
        f'/contatos/loja/{loja.pk}/pdf/',
        {'pdf': _pdf_upload()},
    )
    remove = client.post(f'/contatos/loja/{loja.pk}/pdf/remover/')

    assert upload.status_code == 404
    assert remove.status_code == 404
    assert not LojaPdf.objects.filter(loja=loja).exists()


def test_deleting_empty_loja_removes_its_pdf_file(media_root):
    tenant = _tenant_vale('PDE')
    loja = Loja.objects.create(tenant=tenant, nome='Loja para excluir')
    client = _client(tenant, ROLE_ADM)
    uploaded = client.post(
        f'/contatos/loja/{loja.pk}/pdf/',
        {'pdf': _pdf_upload()},
    )
    assert uploaded.status_code == 302
    pdf = LojaPdf.objects.get(loja=loja)
    file_path = media_root / pdf.arquivo.name
    assert file_path.exists()

    response = client.post(f'/contatos/loja/{loja.pk}/excluir/')

    assert response.status_code == 302
    assert not Loja.objects.filter(pk=loja.pk).exists()
    assert not LojaPdf.objects.filter(pk=loja.pk).exists()
    assert not file_path.exists()
