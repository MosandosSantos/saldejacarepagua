"""Conexão ao banco de dados Sal da Britanea (PostgreSQL).

Fornece a conexão thread-local via psycopg3 com reuso por thread (cada handshake
TCP custa ~120ms — reutilizar corta ~1,5s do dashboard, que faz ~15 consultas
por render).
"""
import logging
import os
import socket
import threading
from contextlib import contextmanager

import psycopg

logger = logging.getLogger(__name__)

# Conexão reutilizada por thread (psycopg não é thread-safe entre threads,
# mas cada thread do servidor mantém a sua — evita handshake a cada consulta).
_tls = threading.local()


class _DummyCursor:
    """Cursor fictício — retorna vazio quando o banco GPRB indisponível."""
    # DB-API: description=None sinaliza consulta sem conjunto de resultados.
    # Sem este atributo, repositórios que leem cur.description quebram com
    # AttributeError no modo degradado (specs/legacy/database.md: telas
    # GPRB renderizam vazias em vez de 500).
    description = None

    def execute(self, *a, **kw): pass
    def fetchone(self): return (0,)
    def fetchall(self): return []
    def __enter__(self): return self
    def __exit__(self, *a): pass


class _DummyConnection:
    """Conexão fictícia — close() é no-op."""
    def cursor(self): return _DummyCursor()
    def close(self): pass
    def __enter__(self): return self
    def __exit__(self, *a): self.close()


class _ConnProxy:
    """Proxy da conexão: `close()` devolve ao pool da thread em vez de fechar.

    Permite reuso transparente — o padrão `finally: conn.close()` dos ~20 call
    sites existentes continua funcionando sem alteração.
    """

    def __init__(self, conn):
        self._conn = conn

    def close(self):
        # No-op: a conexão permanece viva na thread para a próxima consulta.
        # rollback limpa qualquer transação pendente (segurança).
        try:
            self._conn.rollback()
        except (psycopg.Error, OSError) as e:
            logger.debug('Rollback falhou no close do proxy: %s', e)

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _nova_conexao():
    """Abre uma conexão física com o banco saldabritanea."""
    password = None
    pw = os.environ.get('GPRB_DB_PASSWORD')
    if pw:
        # No host (testes, runserver fora do compose) o .env pode ser carregado
        # literal: '$$' é escape do docker compose — volta a ser '$'. Dentro do
        # container o compose já desescapou e '$$' nunca ocorre (no-op).
        password = pw.replace('$$', '$')
    else:
        # Fallback: lê do .env do projeto (aceita GPRB_DB_PASSWORD ou PGPASSWORD)
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    for chave in ('GPRB_DB_PASSWORD=', 'PGPASSWORD='):
                        if line.startswith(chave):
                            # '$$' no .env é escape do docker compose — volta a ser '$'
                            # para leitura direta do arquivo (fora do compose).
                            password = line.split('=', 1)[1].replace('$$', '$')
                            break
                    if password:
                        break
    host = os.environ.get('GPRB_DB_HOST', '127.0.0.1')
    # Se o host for localhost/127.0.0.1 e nao existir o banco, retorna None
    # (modo Docker sem banco GPRB externo)
    if host in ('localhost', '127.0.0.1'):
        try:
            socket.create_connection((host, int(os.environ.get('GPRB_DB_PORT', '5432'))), timeout=2)
        except (OSError, ConnectionRefusedError):
            logger.warning('Banco GPRB indisponivel em %s:%s — modo degradado', host, os.environ.get('GPRB_DB_PORT', '5432'))
            return None
    return psycopg.connect(
        host=host,
        port=int(os.environ.get('GPRB_DB_PORT', '5432')),
        dbname=os.environ.get('GPRB_DB_NAME', 'saldabritanea'),
        user=os.environ.get('GPRB_DB_USER', 'postgres'),
        password=password,
        sslmode=os.environ.get('GPRB_DB_SSLMODE', 'prefer'),
        connect_timeout=int(os.environ.get('GPRB_DB_TIMEOUT', '10')),
        autocommit=True,
    )


def connect():
    """Retorna a conexão da thread (reutilizada) — `close()` é no-op via proxy."""
    conn = getattr(_tls, 'conn', None)
    if conn is not None:
        try:
            if not conn.closed:
                return _ConnProxy(conn)
        except (psycopg.Error, OSError, AttributeError) as e:
            logger.debug('Conexão existente inválida: %s', e)
    # (re)abre a conexão física desta thread
    conn = _nova_conexao()
    if conn is None:
        return _DummyConnection()
    _tls.conn = conn
    return _ConnProxy(conn)


@contextmanager
def gprb_transaction():
    """Transação explícita para escritas multi-statement no banco GPRB.

    A conexão roda em autocommit — cada execute() seria permanente.
    Dentro deste bloco tudo vira uma transação única: COMMIT no sucesso,
    ROLLBACK total em qualquer exceção (nenhum efeito parcial visível).
    Com banco indisponível (modo degradado/dummy) o bloco é no-op.
    Uso: `with gprb_transaction(), gprb_cursor() as cur: ...`
    """
    conn = connect()
    if conn is None or not hasattr(conn, 'transaction'):
        yield None
        return
    with conn.transaction():
        yield conn


def coluna_existe(cur, tabela, coluna):
    """True quando a coluna existe na tabela do GPRB (schema compartilhado varia)."""
    cur.execute(
        'SELECT 1 FROM information_schema.columns '
        'WHERE table_name = %s AND column_name = %s LIMIT 1',
        (tabela, coluna),
    )
    return cur.fetchone() is not None


def _tenant_id_por_codigo(cur, tenant_code='GPRB'):
    cur.execute('SELECT id FROM tenant WHERE code = %s', (tenant_code,))
    row = cur.fetchone()
    return row[0] if row else None
