"""Aplica o schema da feature Potência (DDL idempotente) e remove a tabela legada de emolumentos.

Uso:
    .venv/Scripts/python.exe scripts/aplicar_schema_potencia.py
    # aplica em saldabritanea e saldabritanea_test (ou: ... <db1> <db2>)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.gprb import connection as gconn

DDL = (
    # --- Potência: contatos de cargo + dados financeiros ---
    'ALTER TABLE "prefeitura" ADD COLUMN IF NOT EXISTS "email" text',
    'ALTER TABLE "prefeitura" ADD COLUMN IF NOT EXISTS "secretarioEmail" text',
    'ALTER TABLE "prefeitura" ADD COLUMN IF NOT EXISTS "secretarioTelefone" text',
    'ALTER TABLE "prefeitura" ADD COLUMN IF NOT EXISTS "tesoureiroEmail" text',
    'ALTER TABLE "prefeitura" ADD COLUMN IF NOT EXISTS "tesoureiroTelefone" text',
    'ALTER TABLE "prefeitura" ADD COLUMN IF NOT EXISTS "pix" text',
    'ALTER TABLE "prefeitura" ADD COLUMN IF NOT EXISTS "valorAnuidade" numeric(12,2)',
    'ALTER TABLE "prefeitura" ADD COLUMN IF NOT EXISTS "dataVencimentoAnuidade" date',
    # --- Feature removida: tabela de emolumentos (substituída por PDF por loja) ---
    'DROP TABLE IF EXISTS "emolumento"',
)


def _aplicar(db_name):
    antigo = os.environ.get('GPRB_DB_NAME')
    os.environ['GPRB_DB_NAME'] = db_name
    gconn._tls.conn = None  # força reconexão no banco alvo
    try:
        conn = gconn.connect()
        if isinstance(conn, gconn._DummyConnection):
            raise SystemExit(f'[erro] banco {db_name} indisponível — nada aplicado')
        cur = conn.cursor()
        for stmt in DDL:
            cur.execute(stmt)
        print(f'[ok] {db_name}: {len(DDL)} statements aplicados')
    finally:
        if antigo is None:
            os.environ.pop('GPRB_DB_NAME', None)
        else:
            os.environ['GPRB_DB_NAME'] = antigo
        gconn._tls.conn = None


if __name__ == '__main__':
    alvos = sys.argv[1:] or ['saldabritanea', 'saldabritanea_test']
    for db in alvos:
        _aplicar(db)
