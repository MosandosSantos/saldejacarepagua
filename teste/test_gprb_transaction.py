"""Testes do context manager de transação GPRB (Spec 002, T1).

Valida: COMMIT no sucesso, ROLLBACK total em exceção — contra o banco de
teste `saldabritanea_test` (nunca o banco real).
"""
import pytest

from core.gprb import connection as gconn
from core.gprb.connection import gprb_transaction

pytestmark = pytest.mark.django_db


@pytest.fixture
def scratch(banco_gprb_teste):
    """Tabela rascunho dedicada (criada/descartada por teste)."""
    conn = gconn.connect()
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS test_scratch (id int PRIMARY KEY, valor text)')
    cur.execute('TRUNCATE test_scratch')
    yield
    cur.execute('DROP TABLE IF EXISTS test_scratch')


def test_commit_persiste_dados(banco_gprb_teste, scratch):
    with gprb_transaction():
        cur = gconn.connect().cursor()
        cur.execute("INSERT INTO test_scratch (id, valor) VALUES (1, 'persistido')")
    cur = gconn.connect().cursor()
    cur.execute('SELECT valor FROM test_scratch WHERE id = 1')
    assert cur.fetchone()[0] == 'persistido'


def test_rollback_descarta_tudo_em_excecao(banco_gprb_teste, scratch):
    with pytest.raises(RuntimeError, match='boom'):
        with gprb_transaction():
            cur = gconn.connect().cursor()
            cur.execute("INSERT INTO test_scratch (id, valor) VALUES (2, 'temporario')")
            raise RuntimeError('boom')
    cur = gconn.connect().cursor()
    cur.execute('SELECT COUNT(*) FROM test_scratch WHERE id = 2')
    assert cur.fetchone()[0] == 0  # nada ficou gravado


def test_padrao_repositorio_transaction_com_cursor(banco_gprb_teste, scratch):
    """Integração: `with gprb_transaction(), gprb_cursor() as cur` (padrão do repositório)."""
    from repositories.gprb_repository import gprb_cursor

    with gprb_transaction(), gprb_cursor() as cur:
        cur.execute("INSERT INTO test_scratch (id, valor) VALUES (3, 'via_repo')")
    cur = gconn.connect().cursor()
    cur.execute('SELECT COUNT(*) FROM test_scratch WHERE id = 3')
    assert cur.fetchone()[0] == 1
