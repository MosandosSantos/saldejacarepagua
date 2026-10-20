from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.core import mail
from django.test import override_settings

from core.gprb import connection as gprb_connection
from core.gprb import users as gprb_users
from repositories import gprb_repository as repo


@pytest.fixture
def target_and_foreign_entities(banco_gprb_teste):
    suffix = uuid4().hex
    data = {
        'target_code': f'SCG_ISO_{suffix}',
        'foreign_code': f'OTHER_ISO_{suffix}',
        'target_tenant': f'tenant-target-{suffix}',
        'foreign_tenant': f'tenant-foreign-{suffix}',
        'target_prefeitura': f'pref-target-{suffix}',
        'foreign_prefeitura': f'pref-foreign-{suffix}',
        'target_loja': f'loja-target-{suffix}',
        'foreign_loja': f'loja-foreign-{suffix}',
        'target_member': f'member-target-{suffix}',
        'foreign_member': f'member-foreign-{suffix}',
        'foreign_user': f'user-foreign-{suffix}',
        'target_rito': f'TARGET_RITO_{suffix}',
        'foreign_rito': f'FOREIGN_RITO_{suffix}',
        'target_loja_name': f'Loja do tenant {suffix}',
        'foreign_loja_name': f'Loja de outro tenant {suffix}',
    }
    conn = gprb_connection.connect()
    cur = conn.cursor()
    for tenant_key, code_key in (
        ('target_tenant', 'target_code'), ('foreign_tenant', 'foreign_code'),
    ):
        cur.execute(
            'INSERT INTO tenant (id, code, name, "createdAt", "updatedAt") '
            'VALUES (%s, %s, %s, NOW(), NOW())',
            (data[tenant_key], data[code_key], 'Tenant de isolamento'),
        )
    for tenant_key, prefeitura_key, loja_key, member_key, rito_key in (
        ('target_tenant', 'target_prefeitura', 'target_loja', 'target_member', 'target_rito'),
        ('foreign_tenant', 'foreign_prefeitura', 'foreign_loja', 'foreign_member', 'foreign_rito'),
    ):
        loja_prefeitura_id = (
            data['target_prefeitura'] if tenant_key == 'foreign_tenant' else data[prefeitura_key]
        )
        cur.execute(
            'INSERT INTO prefeitura (id, "tenantId", nome, sigla, status, "createdAt", "updatedAt") '
            'VALUES (%s, %s, %s, %s, %s, NOW(), NOW())',
            (data[prefeitura_key], data[tenant_key], 'Potência de teste', 'PT', 'ATIVA'),
        )
        cur.execute(
            'INSERT INTO loja (id, "tenantId", "lojaMX", "prefeituraId", "nomeFantasia", '
            '"createdAt", "updatedAt") VALUES (%s, %s, %s, %s, %s, NOW(), NOW())',
            (
                data[loja_key], data[tenant_key], 'LT', loja_prefeitura_id,
                data['target_loja_name'] if tenant_key == 'target_tenant' else data['foreign_loja_name'],
            ),
        )
        cur.execute(
            'INSERT INTO member (id, "tenantId", "nomeCompleto", cpf, email, celular, '
            '"enderecoLogradouro", "enderecoCep", "enderecoCidade", "enderecoUf", rito, '
            '"lojaId", situacao, "createdAt", "updatedAt") '
            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())',
            (
                data[member_key], data[tenant_key], 'Membro de teste',
                f'{suffix[:10]}{tenant_key[0]}', f'{data[member_key]}@teste.invalid',
                '21900000000', 'Rua Teste', '00000-000', 'Rio de Janeiro', 'RJ',
                data[rito_key], data[loja_key] if tenant_key == 'foreign_tenant' else None,
                'ATIVO',
            ),
        )
    cur.execute(
        'INSERT INTO member_loja ("memberId", "lojaId") VALUES (%s, %s)',
        (data['foreign_member'], data['foreign_loja']),
    )
    cur.execute(
        'INSERT INTO "user" (id, "tenantId", email, name, role, status, "createdAt", "updatedAt") '
        'VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())',
        (
            data['foreign_user'], data['foreign_tenant'],
            f'{data["foreign_user"]}@teste.invalid', 'Usuário de outro tenant',
            'MEMBER', 'ACTIVE',
        ),
    )
    try:
        yield data
    finally:
        cur.execute('DELETE FROM "user" WHERE id = %s', (data['foreign_user'],))
        cur.execute(
            'DELETE FROM member_loja WHERE "memberId" = ANY(%s) OR "lojaId" = ANY(%s)',
            ([data['target_member'], data['foreign_member']],
             [data['target_loja'], data['foreign_loja']]),
        )
        cur.execute(
            'DELETE FROM member WHERE id = ANY(%s)',
            ([data['target_member'], data['foreign_member']],),
        )
        cur.execute(
            'DELETE FROM loja WHERE id = ANY(%s)',
            ([data['target_loja'], data['foreign_loja']],),
        )
        cur.execute(
            'DELETE FROM prefeitura WHERE id = ANY(%s)',
            ([data['target_prefeitura'], data['foreign_prefeitura']],),
        )
        cur.execute(
            'DELETE FROM tenant WHERE id = ANY(%s)',
            ([data['target_tenant'], data['foreign_tenant']],),
        )
        conn.close()


@pytest.mark.django_db(transaction=True)
def test_direct_lookups_hide_other_tenant_entities(target_and_foreign_entities):
    data = target_and_foreign_entities
    with override_settings(GPRB_TENANT_CODE=data['target_code']):
        assert repo.buscar_membro(data['foreign_member']) is None
        assert repo.buscar_loja(data['foreign_loja']) is None
        assert repo.buscar_loja_para_edicao(data['foreign_loja']) is None
        assert repo.buscar_prefeitura(data['foreign_prefeitura']) is None
        assert repo.contar_membros_loja(data['foreign_loja']) == 0
        assert repo.contar_lojas_prefeitura(data['foreign_prefeitura']) == 0


@pytest.mark.django_db(transaction=True)
def test_direct_mutations_do_not_change_other_tenant_entities(target_and_foreign_entities):
    data = target_and_foreign_entities
    with override_settings(GPRB_TENANT_CODE=data['target_code']):
        repo.atualizar_membro(data['foreign_member'], {'nomeCompleto': 'Alterado'})
        repo.inativar_membro(data['foreign_member'])
        repo.excluir_membro(data['foreign_member'])
        repo.atualizar_loja(data['foreign_loja'], {
            'nome': 'Loja alterada', 'prefeitura_id': data['foreign_prefeitura'],
        })
        with pytest.raises(ValueError):
            repo.criar_loja({
                'nome': 'Loja com potência estrangeira',
                'prefeitura_id': data['foreign_prefeitura'],
            })
        repo.excluir_loja(data['foreign_loja'])
        repo.atualizar_prefeitura(data['foreign_prefeitura'], {'nome': 'Potência alterada'})
        repo.excluir_prefeitura(data['foreign_prefeitura'])

    cur = gprb_connection.connect().cursor()
    cur.execute('SELECT "nomeCompleto", situacao FROM member WHERE id = %s', (data['foreign_member'],))
    assert cur.fetchone() == ('Membro de teste', 'ATIVO')
    cur.execute('SELECT "nomeFantasia" FROM loja WHERE id = %s', (data['foreign_loja'],))
    assert cur.fetchone() == (data['foreign_loja_name'],)
    cur.execute('SELECT "prefeituraId" FROM loja WHERE id = %s', (data['foreign_loja'],))
    assert cur.fetchone()[0] == data['target_prefeitura']
    cur.execute('SELECT nome FROM prefeitura WHERE id = %s', (data['foreign_prefeitura'],))
    assert cur.fetchone() == ('Potência de teste',)


@pytest.mark.django_db(transaction=True)
def test_selects_and_autocomplete_hide_other_tenant_data(target_and_foreign_entities):
    data = target_and_foreign_entities
    with override_settings(GPRB_TENANT_CODE=data['target_code']):
        stores = repo.listar_lojas_select()
        prefeitura_options = repo.listar_lojas_para_select()
        distinct_ritos = repo.valores_distintos('rito')
        listed_stores, _ = repo.listar_lojas()
        members = repo.listar_membros({})
        member = repo.buscar_membro(data['target_member'])
        prefeituras, _, _, _ = repo.listar_prefeituras()
        assert data['target_loja'] in {store['id'] for store in stores}
        assert data['foreign_loja'] not in {store['id'] for store in stores}
        assert {row['id'] for row in prefeitura_options} == {data['target_prefeitura']}
        assert {loja['id'] for loja in listed_stores} == {data['target_loja']}
        assert {row[0] for row in members} == {data['target_member']}
        assert data['foreign_loja_name'] not in repr(members)
        assert member['lojas'] == []
        assert {prefeitura['id'] for prefeitura in prefeituras} == {data['target_prefeitura']}
        assert data['target_rito'] in distinct_ritos
        assert data['foreign_rito'] not in distinct_ritos
        assert prefeituras[0]['total_lojas'] == 1
        assert repo.listar_membros_loja(data['foreign_loja']) == []
        assert repo.listar_lojas_por_prefeitura(data['foreign_prefeitura']) == []


@pytest.mark.django_db(transaction=True)
def test_member_cannot_be_linked_to_foreign_tenant_shop(target_and_foreign_entities):
    data = target_and_foreign_entities
    with override_settings(GPRB_TENANT_CODE=data['target_code']):
        assert gprb_connection.resolve_tenant_code() == data['target_code']
        with pytest.raises(ValueError):
            repo.definir_lojas_membro(data['target_member'], [data['foreign_loja']])
        with pytest.raises(ValueError):
            repo.atualizar_membro(data['target_member'], {'lojaId': data['foreign_loja']})

    cur = gprb_connection.connect().cursor()
    cur.execute('SELECT "lojaId" FROM member WHERE id = %s', (data['target_member'],))
    assert cur.fetchone()[0] is None


@pytest.mark.django_db(transaction=True)
def test_user_management_by_id_is_scoped_to_configured_tenant(target_and_foreign_entities):

    data = target_and_foreign_entities
    with override_settings(GPRB_TENANT_CODE=data['target_code']):
        assert not gprb_users.atualizar_usuario_sistema(
            data['foreign_user'], nome='Alterado', email='alterado@example.test',
            celular='21911111111', role='MEMBER',
        )
        assert not gprb_users.excluir_usuario_sistema(data['foreign_user'])

    cur = gprb_connection.connect().cursor()
    cur.execute('SELECT name, email, "deletedAt" FROM "user" WHERE id = %s', (data['foreign_user'],))
    assert cur.fetchone() == (
        'Usuário de outro tenant', f'{data["foreign_user"]}@teste.invalid', None,
    )


@pytest.mark.django_db(transaction=True)
@override_settings(
    EMAIL_CONFIGURADO=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
def test_event_email_only_targets_configured_tenant_members(target_and_foreign_entities):
    data = target_and_foreign_entities
    cur = gprb_connection.connect().cursor()
    cur.execute(
        'UPDATE member SET "lojaId" = %s WHERE id = ANY(%s)',
        (data['target_loja'], [data['target_member'], data['foreign_member']]),
    )
    evento = SimpleNamespace(
        loja_id=data['target_loja'],
        titulo='Sessão de teste',
        data_inicio=datetime.now(),
        data_fim=datetime.now() + timedelta(hours=2),
        descricao='',
        get_tipo_display=lambda: 'Ritualística',
    )
    mail.outbox.clear()

    with override_settings(GPRB_TENANT_CODE=data['target_code']):
        from tarefas.views import _enviar_email_novo_evento

        _enviar_email_novo_evento(evento)

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [f'{data["target_member"]}@teste.invalid']
