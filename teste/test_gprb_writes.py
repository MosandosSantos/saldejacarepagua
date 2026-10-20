"""Testes das escritas GPRB com atomicidade (Spec 002, T2/T5).

Cobre `definir_lojas_membro` (o caso crítico: DELETE→INSERTs→UPDATE) e
`inativar_membro` contra o banco de teste `saldabritanea_test`.
"""
from contextlib import contextmanager

import pytest

from core.gprb import connection as gconn
from repositories import gprb_repository as repo

pytestmark = pytest.mark.django_db


@pytest.fixture
def seed_gprb(banco_gprb_teste):
    """Tenant GPRB + potência + 2 lojas + 1 membro no banco de teste."""
    conn = gconn.connect()
    cur = conn.cursor()
    tid, pid = 'test-tenant-0001', 'test-pf-0001'
    mid = 'test-mem-0001'
    lojas = ['test-loja-0001', 'test-loja-0002']
    # idempotência: limpa restos de execuções anteriores
    cur.execute('DELETE FROM member_loja WHERE "memberId" = %s OR "lojaId" = ANY(%s)', (mid, lojas))
    cur.execute('DELETE FROM member WHERE id = %s', (mid,))
    cur.execute('DELETE FROM loja WHERE id = ANY(%s)', (lojas,))
    cur.execute('DELETE FROM prefeitura WHERE id = %s', (pid,))
    cur.execute('DELETE FROM tenant WHERE id = %s', (tid,))
    cur.execute(
        'INSERT INTO tenant (id, code, name, "createdAt", "updatedAt") '
        'VALUES (%s, %s, %s, NOW(), NOW()) ON CONFLICT (id) DO NOTHING',
        (tid, 'GPRB', 'Sal da Britânea (teste)'),
    )
    cur.execute(
        'INSERT INTO prefeitura (id, "tenantId", nome, status, "createdAt", "updatedAt") '
        'VALUES (%s, %s, %s, %s, NOW(), NOW()) ON CONFLICT (id) DO NOTHING',
        (pid, tid, 'Potência Teste', 'ATIVA'),
    )
    for i, lid in enumerate(lojas, 1):
        cur.execute(
            'INSERT INTO loja (id, "tenantId", "lojaMX", "prefeituraId", "nomeFantasia", '
            '"createdAt", "updatedAt") VALUES (%s, %s, %s, %s, %s, NOW(), NOW())',
            (lid, tid, f'LT{i}', pid, f'Loja Teste {i}'),
        )
    cur.execute(
        'INSERT INTO member (id, "tenantId", "nomeCompleto", cpf, email, celular, '
        '"enderecoLogradouro", "enderecoCep", "enderecoCidade", "enderecoUf", '
        'situacao, "createdAt", "updatedAt") '
        'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())',
        (mid, tid, 'Membro Teste', '000.000.000-00', 'membro@teste.com',
         '(21) 90000-0000', 'Rua Teste', '00000-000', 'Rio de Janeiro', 'RJ', 'ATIVO'),
    )
    yield {'tenant': tid, 'prefeitura': pid, 'lojas': lojas, 'member': mid}
    # limpeza (ordem segura)
    cur.execute('DELETE FROM member_loja WHERE "memberId" = %s', (mid,))
    cur.execute('DELETE FROM member WHERE id = %s', (mid,))
    for lid in lojas:
        cur.execute('DELETE FROM loja WHERE id = %s', (lid,))
    cur.execute('DELETE FROM prefeitura WHERE id = %s', (pid,))
    cur.execute('DELETE FROM tenant WHERE id = %s', (tid,))


def _vinculos(member_id):
    cur = gconn.connect().cursor()
    cur.execute(
        'SELECT "lojaId", "dataInclusao" FROM member_loja '
        'WHERE "memberId" = %s ORDER BY "lojaId"',
        (member_id,),
    )
    return cur.fetchall()


def test_definir_lojas_cria_vinculos_e_define_principal(seed_gprb):
    repo.definir_lojas_membro(seed_gprb['member'], seed_gprb['lojas'])
    vinculos = _vinculos(seed_gprb['member'])
    assert {v[0] for v in vinculos} == set(seed_gprb['lojas'])
    # primeira loja da lista vira principal
    cur = gconn.connect().cursor()
    cur.execute('SELECT "lojaId" FROM member WHERE id = %s', (seed_gprb['member'],))
    assert cur.fetchone()[0] == seed_gprb['lojas'][0]


def test_data_inclusao_preservada_ao_redefinir(seed_gprb):
    from datetime import date

    repo.definir_lojas_membro(seed_gprb['member'], seed_gprb['lojas'])
    data_original = _vinculos(seed_gprb['member'])[0][1]
    # redefinir SEM informar datas → data original da loja já vinculada é mantida
    repo.definir_lojas_membro(seed_gprb['member'], seed_gprb['lojas'])
    for v in _vinculos(seed_gprb['member']):
        assert v[1] == data_original
    # redefinir COM data explícita → aplica a nova
    nova = date(2019, 5, 10)
    repo.definir_lojas_membro(
        seed_gprb['member'], seed_gprb['lojas'],
        datas_inclusao={seed_gprb['lojas'][0]: nova},
    )
    por_loja = {v[0]: v[1] for v in _vinculos(seed_gprb['member'])}
    assert por_loja[seed_gprb['lojas'][0]] == nova


def test_definir_lojas_sem_lojas_zera_principal(seed_gprb):
    repo.definir_lojas_membro(seed_gprb['member'], seed_gprb['lojas'])
    repo.definir_lojas_membro(seed_gprb['member'], [])
    assert _vinculos(seed_gprb['member']) == []
    cur = gconn.connect().cursor()
    cur.execute('SELECT "lojaId" FROM member WHERE id = %s', (seed_gprb['member'],))
    assert cur.fetchone()[0] is None  # membro sem loja é válido


def test_definir_lojas_rollback_em_falha_no_meio(seed_gprb, monkeypatch):
    """O caso crítico da spec 002: falha no UPDATE final não pode deixar
    member_loja parcialmente apagada (transação única com ROLLBACK)."""
    member_id = seed_gprb['member']
    repo.definir_lojas_membro(member_id, seed_gprb['lojas'])
    antes = _vinculos(member_id)
    assert len(antes) == 2

    class _CursorFalho:
        """Cursor real que estoura ao chegar no UPDATE member (última etapa)."""

        def __init__(self, real):
            self._real = real

        def execute(self, sql, *args, **kwargs):
            if 'UPDATE member' in sql:
                raise RuntimeError('falha proposital no meio da escrita')
            return self._real.execute(sql, *args, **kwargs)

        def __getattr__(self, nome):
            return getattr(self._real, nome)

    cursor_original = repo.gprb_cursor  # captura ANTES do monkeypatch

    @contextmanager
    def cursor_falho():
        with cursor_original() as real:
            yield _CursorFalho(real)

    monkeypatch.setattr(repo, 'gprb_cursor', cursor_falho)
    with pytest.raises(RuntimeError, match='falha proposital'):
        repo.definir_lojas_membro(member_id, [seed_gprb['lojas'][0]])
    monkeypatch.undo()

    # ROLLBACK comprovado: vínculos permanecem exatamente como antes
    depois = _vinculos(member_id)
    assert depois == antes


def test_inativar_membro(seed_gprb):
    repo.inativar_membro(seed_gprb['member'])
    cur = gconn.connect().cursor()
    cur.execute('SELECT situacao FROM member WHERE id = %s', (seed_gprb['member'],))
    assert cur.fetchone()[0] == 'INATIVO'
