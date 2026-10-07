"""Modo degradado do banco GPRB — contrato das telas sem Postgres externo.

specs/legacy/database.md: "Postgres indisponível → modo degradado
(`_DummyCursor`), telas GPRB renderizam vazias em vez de 500."
Regressão: /dashboard/ estourava AttributeError em cur.description quando o
container subia sem acesso ao banco GPRB (docker compose sem GPRB_DB_HOST).
"""
from core.gprb.connection import _DummyConnection, _DummyCursor
from dashboard.repositories.gprb_repository import GprbRepository


def _repo_degradado():
    return GprbRepository(connect_fn=lambda: _DummyConnection())


def test_dummy_cursor_nao_tem_conjunto_de_resultados():
    """DB-API: description=None quando a consulta não gera resultados."""
    cur = _DummyCursor()
    cur.execute('SELECT 1')
    assert cur.description is None
    assert cur.fetchall() == []


def test_fetch_one_kpis_retorna_none_em_modo_degradado():
    """dashboard_kpis não pode vazar a tupla crua do cursor dummy.

    Consumidores fazem `dashboard_kpis() or {}` e depois `.get(...)`;
    uma tupla (0,) truthy quebraria o .get com AttributeError.
    """
    assert _repo_degradado().dashboard_kpis() is None


def test_fetch_all_retorna_lista_vazia_em_modo_degradado():
    assert _repo_degradado().membros_por_situacao() == []
    assert _repo_degradado().membros_por_rito() == []


def test_fetchone_count_dummy_mantem_zero_para_chamadas_posicionais():
    """`cur.fetchone()[0]` em COUNTs continua seguro com o dummy."""
    cur = _DummyConnection().cursor()
    cur.execute('SELECT COUNT(*) FROM member')
    assert cur.fetchone()[0] == 0


def test_autenticacao_gprb_degradada_cai_no_local_sem_excecao(monkeypatch):
    """Sem banco GPRB: autentica/existe respondem 'não encontrado' silenciosamente.

    Regressão: autenticar_usuario desempacotava a linha dummy (0,) esperando 8
    colunas → ValueError logado como ERROR a cada login. E existe_usuario
    respondia True com o dummy — se autenticar parasse de lançar, o login
    local seria bloqueado ('Login ou senha inválidos') no modo degradado.
    """
    import core.gprb.users as users_mod
    monkeypatch.setattr(users_mod, 'connect', lambda: _DummyConnection())
    assert users_mod.autenticar_usuario('load-test@local.test', 'senha') is None
    assert users_mod.existe_usuario('load-test@local.test') is False
