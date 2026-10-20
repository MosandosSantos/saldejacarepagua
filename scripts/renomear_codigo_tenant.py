"""Renomeia com guarda o código de um tenant no banco externo GPRB."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.gprb.connection import connect


class TenantCodeRenameError(ValueError):
    """A pré-condição para renomear o tenant não foi satisfeita."""


def renomear_codigo_tenant(conn, codigo_atual: str, codigo_novo: str, *, apply=False) -> str:
    """Valida e, se `apply=True`, atualiza somente o código do tenant."""
    atual = (codigo_atual or '').strip()
    novo = (codigo_novo or '').strip()
    if not atual or not novo or atual == novo:
        raise TenantCodeRenameError('Informe dois códigos de tenant distintos e não vazios.')

    raw_conn = getattr(conn, '_conn', conn)
    with raw_conn.transaction():
        with raw_conn.cursor() as cursor:
            cursor.execute('LOCK TABLE tenant IN ACCESS EXCLUSIVE MODE')
            cursor.execute('SELECT id FROM tenant WHERE code = %s FOR UPDATE', (atual,))
            old_rows = cursor.fetchall()
            if len(old_rows) != 1:
                raise TenantCodeRenameError(
                    f'Esperava exatamente um tenant com código {atual}; encontrei {len(old_rows)}.'
                )

            tenant_id = old_rows[0][0]
            cursor.execute('SELECT id FROM tenant WHERE code = %s', (novo,))
            new_rows = cursor.fetchall()
            if new_rows:
                raise TenantCodeRenameError(
                    f'O código de destino {novo} já existe em {len(new_rows)} tenant(s).'
                )

            if not apply:
                return tenant_id

            cursor.execute(
                'UPDATE tenant SET code = %s WHERE id = %s AND code = %s',
                (novo, tenant_id, atual),
            )
            if cursor.rowcount != 1:
                raise TenantCodeRenameError(
                    f'A atualização de {atual} para {novo} alterou {cursor.rowcount} linha(s).'
                )

            cursor.execute('SELECT id FROM tenant WHERE code = %s', (novo,))
            new_rows = cursor.fetchall()
            if new_rows != [(tenant_id,)]:
                raise TenantCodeRenameError('A verificação pós-atualização do tenant falhou.')
            return tenant_id


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old', required=True, help='código atual do tenant')
    parser.add_argument('--new', required=True, help='novo código do mesmo tenant')
    parser.add_argument(
        '--apply', action='store_true',
        help='efetua a atualização; sem esta opção, somente valida e simula',
    )
    args = parser.parse_args(argv)

    conn = connect()
    if not hasattr(conn, '_conn'):
        print('Banco GPRB externo indisponível; nenhuma alteração foi feita.', file=sys.stderr)
        return 1

    try:
        tenant_id = renomear_codigo_tenant(
            conn, args.old, args.new, apply=args.apply,
        )
    except TenantCodeRenameError as exc:
        print(f'Operação cancelada: {exc}', file=sys.stderr)
        return 1
    finally:
        conn.close()

    acao = 'renomeado' if args.apply else 'dry-run; seria renomeado'
    print(f'Tenant id={tenant_id} {acao}: {args.old} -> {args.new}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
