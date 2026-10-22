"""Compara a estrutura de dois bancos PostgreSQL (tabelas, colunas, constraints,
indices e migrations aplicadas) e lista as diferencas.

Uso:
    python scripts/comparar_schema.py ORIGEM_URL DESTINO_URL
    python scripts/comparar_schema.py --origem-env DATABASE_URL --destino-env OUTRA_URL

Codigos de saida:
    0 = estruturas identicas
    1 = diferencas encontradas
    2 = erro de conexao/argumento
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from dataclasses import dataclass

import psycopg

SISTEMAS = ('pg_catalog', 'information_schema')

TABELAS = f"""
    select table_schema, table_name
    from information_schema.tables
    where table_type = 'BASE TABLE'
      and table_schema not in {SISTEMAS}
"""

COLUNAS = f"""
    select table_schema, table_name, column_name, data_type, udt_name,
           is_nullable, coalesce(column_default, ''),
           coalesce(character_maximum_length, -1),
           coalesce(numeric_precision, -1),
           coalesce(numeric_scale, -1)
    from information_schema.columns
    where table_schema not in {SISTEMAS}
"""

CONSTRAINTS = f"""
    select n.nspname, c.relname, con.conname, con.contype,
           pg_get_constraintdef(con.oid)
    from pg_constraint con
    join pg_class c on c.oid = con.conrelid
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname not in {SISTEMAS}
"""

INDICES = f"""
    select schemaname, tablename, indexname, indexdef
    from pg_indexes
    where schemaname not in {SISTEMAS}
"""

# Extensoes nao fazem parte do schema logico da aplicacao.
IGNORAR_TABELAS = {'spatial_ref_sys'}


@dataclass
class Estrutura:
    tabelas: set
    colunas: dict
    constraints: set
    indices: set
    migrations: set


def _normalizar(sql: str) -> str:
    return ' '.join(sql.split())


def ler_estrutura(url: str) -> Estrutura:
    with psycopg.connect(url) as conexao:
        tabelas = {
            (schema, nome)
            for schema, nome in conexao.execute(TABELAS)
            if nome not in IGNORAR_TABELAS
        }
        colunas = {
            (schema, tabela, coluna): (
                tipo, udt, nulo, padrao, tamanho, precisao, escala,
            )
            for (
                schema, tabela, coluna, tipo, udt, nulo, padrao,
                tamanho, precisao, escala,
            ) in conexao.execute(COLUNAS)
        }
        constraints = {
            (schema, tabela, nome, tipo, _normalizar(definicao))
            for schema, tabela, nome, tipo, definicao in conexao.execute(CONSTRAINTS)
        }
        indices = {
            (schema, tabela, nome, _normalizar(definicao))
            for schema, tabela, nome, definicao in conexao.execute(INDICES)
        }
        try:
            migrations = {
                (app, nome) for app, nome in conexao.execute(
                    'select app, name from django_migrations'
                )
            }
        except psycopg.errors.UndefinedTable:
            conexao.rollback()
            migrations = set()
    return Estrutura(tabelas, colunas, constraints, indices, migrations)


def _por_tabela(chaves_valores):
    agrupado = defaultdict(list)
    for chave in chaves_valores:
        agrupado[chave[:2]].append(chave[2:])
    return agrupado


def comparar(origem: Estrutura, destino: Estrutura) -> list[str]:
    linhas: list[str] = []

    def bloco(titulo, so_origem, so_destino, rotulo_a, rotulo_b, detalhe=None):
        if not so_origem and not so_destino:
            return
        linhas.append(f'\n{titulo}:')
        for chave in sorted(so_origem):
            extra = detalhe.get(chave, '') if detalhe else ''
            linhas.append(f'  - so em {rotulo_a}: {_fmt(chave)}{extra}')
        for chave in sorted(so_destino):
            extra = detalhe.get(chave, '') if detalhe else ''
            linhas.append(f'  - so em {rotulo_b}: {_fmt(chave)}{extra}')

    so_a = origem.tabelas - destino.tabelas
    so_b = destino.tabelas - origem.tabelas
    bloco('TABELAS', so_a, so_b, 'origem', 'destino')

    chaves_a = set(origem.colunas)
    chaves_b = set(destino.colunas)
    divergentes = {
        chave: f'  [{origem.colunas[chave]} != {destino.colunas[chave]}]'
        for chave in chaves_a & chaves_b
        if origem.colunas[chave] != destino.colunas[chave]
    }
    bloco(
        'COLUNAS', chaves_a - chaves_b, chaves_b - chaves_a,
        'origem', 'destino', divergentes,
    )
    if divergentes:
        linhas.append('\nCOLUNAS com tipo/default diferente:')
        for chave in sorted(divergentes):
            linhas.append(
                f'  - {_fmt(chave)}: origem={origem.colunas[chave]} '
                f'destino={destino.colunas[chave]}',
            )

    bloco(
        'CONSTRAINTS', origem.constraints - destino.constraints,
        destino.constraints - origem.constraints, 'origem', 'destino',
    )
    bloco(
        'INDICES', origem.indices - destino.indices,
        destino.indices - origem.indices, 'origem', 'destino',
    )
    bloco(
        'MIGRATIONS', origem.migrations - destino.migrations,
        destino.migrations - origem.migrations, 'origem', 'destino',
    )
    return linhas


def _fmt(chave) -> str:
    return '.'.join(str(parte) for parte in chave)


def _url_do_arg(valor: str | None, env: str | None) -> str:
    url = valor or (os.environ.get(env, '') if env else '')
    if not url:
        raise SystemExit(f'Informe a URL ({env or "argumento"}) do banco.')
    return url


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('origem', nargs='?', help='URL do banco de referencia')
    parser.add_argument('destino', nargs='?', help='URL do banco a comparar')
    parser.add_argument('--origem-env', help='Variavel de ambiente com a URL de origem')
    parser.add_argument('--destino-env', help='Variavel de ambiente com a URL de destino')
    args = parser.parse_args(argv)

    url_origem = _url_do_arg(args.origem, args.origem_env)
    url_destino = _url_do_arg(args.destino, args.destino_env)

    try:
        origem = ler_estrutura(url_origem)
        destino = ler_estrutura(url_destino)
    except psycopg.Error as exc:
        print(f'Erro ao conectar: {exc}', file=sys.stderr)
        return 2

    linhas = comparar(origem, destino)
    if not linhas:
        print('Estruturas identicas (tabelas, colunas, constraints, indices e migrations).')
        return 0

    print('Diferencas encontradas:')
    print('\n'.join(linhas))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
