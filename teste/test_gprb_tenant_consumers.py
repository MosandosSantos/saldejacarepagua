from uuid import uuid4

import pytest
from django.test import override_settings

from core.gprb import connection as gprb_connection
from dashboard.repositories.gprb_repository import GprbRepository
from repositories.gprb_repository import listar_membros, membros_por_situacao


@pytest.fixture
def configured_tenant_members(banco_gprb_teste):
    suffix = uuid4().hex
    tenant_code = f'SCG33REAA_TEST_{suffix}'
    tenant_id = f'tenant-{suffix}'
    member_ids = [f'member-{suffix}-{index}' for index in range(1, 3)]
    status = f'SCG_ONLY_{suffix}'
    conn = gprb_connection.connect()
    cur = conn.cursor()
    cur.execute(
        'SELECT COUNT(*) FROM member m JOIN tenant t ON m."tenantId" = t.id '
        'WHERE t.code = %s',
        ('GPRB',),
    )
    gprb_member_count = cur.fetchone()[0]
    expected_count = gprb_member_count + 1
    member_ids = [f'member-{suffix}-{index}' for index in range(expected_count)]
    cur.execute(
        'INSERT INTO tenant (id, code, name, "createdAt", "updatedAt") '
        'VALUES (%s, %s, %s, NOW(), NOW())',
        (tenant_id, tenant_code, 'Tenant de teste SCG'),
    )
    try:
        for index, member_id in enumerate(member_ids):
            cur.execute(
                'INSERT INTO member (id, "tenantId", "nomeCompleto", cpf, email, celular, '
                '"enderecoLogradouro", "enderecoCep", "enderecoCidade", "enderecoUf", '
                'situacao, "createdAt", "updatedAt") '
                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())',
                (
                    member_id,
                    tenant_id,
                    f'Membro Teste {index}',
                    f'{suffix[:10]}{index}',
                    f'{member_id}@teste.invalid',
                    '21900000000',
                    'Rua Teste',
                    '00000-000',
                    'Rio de Janeiro',
                    'RJ',
                    status,
                ),
            )
        yield {
            'tenant_code': tenant_code,
            'tenant_id': tenant_id,
            'member_ids': member_ids,
            'status': status,
            'expected_count': expected_count,
        }
    finally:
        cur.execute('DELETE FROM member WHERE id = ANY(%s)', (member_ids,))
        cur.execute('DELETE FROM tenant WHERE id = %s', (tenant_id,))
        conn.close()


@pytest.mark.django_db(transaction=True)
def test_gprb_repository_defaults_to_configured_tenant(configured_tenant_members):
    data = configured_tenant_members
    with override_settings(GPRB_TENANT_CODE=data['tenant_code']):
        counts = membros_por_situacao(apenas_ativos=False)
        assert {'name': data['status'], 'total': data['expected_count']} in counts


@pytest.mark.django_db(transaction=True)
def test_dashboard_defaults_to_configured_tenant(configured_tenant_members):
    data = configured_tenant_members
    with override_settings(GPRB_TENANT_CODE=data['tenant_code']):
        result = GprbRepository().dashboard_kpis()
        assert result['total_membros'] == data['expected_count']


@pytest.mark.django_db(transaction=True)
def test_member_listing_uses_configured_tenant(configured_tenant_members):
    data = configured_tenant_members
    with override_settings(GPRB_TENANT_CODE=data['tenant_code']):
        members = listar_membros({})
        returned_ids = {row[0] for row in members}
        assert set(data['member_ids']).issubset(returned_ids)
