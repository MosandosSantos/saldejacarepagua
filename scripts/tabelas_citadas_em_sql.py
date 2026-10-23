"""Extrai as tabelas citadas em SQL nos arquivos do projeto.

Le .py e .sql procurando `FROM/JOIN/INTO/UPDATE/TABLE <nome>` em qualquer
lugar (inclusive dentro de strings multi-linha) e imprime os nomes referenciados
com os arquivos onde aparecem.

Uso: python scripts/tabelas_citadas_em_sql.py
"""

from __future__ import annotations

import os
import re
from collections import defaultdict

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

IGNORAR_DIR = {
    '.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache',
    '.mypy_cache', '.ruff_cache', 'staticfiles', 'media', 'logs', 'htmlcov',
    '.agents', '.github', '.opencode', '.claude', '.codex', '.specify',
    '.playwright-mcp', '.freebuff', '.impeccable', 'theme', 'DOCS',
}

PALAVRAS = r'(?:from|join|into|update|table|exists)'
PADRAO = re.compile(
    rf'\b{PALAVRAS}\s+"?([a-zA-Z_][a-zA-Z0-9_]*)"?',
    re.IGNORECASE,
)

# Palavras que o regex captura mas nao sao tabelas.
RUIDO = {
    'select', 'values', 'set', 'where', 'the', 'a', 'an', 'this', 'it',
    'datetime', 'date', 'import', 'future', 'typing', 'collections', 'os',
    'sys', 're', 'json', 'math', 'uuid', 'string', 'list', 'dict',
    'objects', 'self', 'super', 'defaultdict', 'contextlib', 'pathlib',
    'decimal', 'dataclasses', 'django', 'psycopg', 'requests', 'logging',
    'threading', 'socket', 'functools', 'itertools', 'random', 'base64',
    'textwrap', 'unicodedata', 'urllib', 'smtplib', 'email', 'csv', 'io',
    'tempfile', 'shutil', 'subprocess', 'glob', 'time', 'calendar',
    'mock', 'pytest', 'factory', 'faker', 'secrets', 'hashlib', 'hmac',
    'environ', 'getenv', 'str', 'int', 'float', 'bool', 'set', 'any',
    'all', 'print', 'len', 'range', 'enumerate', 'zip', 'map', 'filter',
    'sum', 'min', 'max', 'round', 'abs', 'sorted', 'reversed', 'open',
    'range', 'the', 'and', 'or', 'not', 'in', 'is', 'if', 'else', 'for',
    'while', 'return', 'class', 'def', 'with', 'as', 'try', 'except',
    'finally', 'raise', 'yield', 'lambda', 'global', 'nonlocal', 'pass',
    'break', 'continue', 'del', 'assert', 'async', 'await', 'match', 'case',
}


def arquivos():
    for pasta, subpastas, nomes in os.walk(RAIZ):
        subpastas[:] = [s for s in subpastas if s not in IGNORAR_DIR]
        for nome in nomes:
            if os.path.splitext(nome)[1] not in {'.py', '.sql'}:
                continue
            caminho = os.path.join(pasta, nome)
            relativo = os.path.relpath(caminho, RAIZ).replace(os.sep, '/')
            if '/migrations/' in relativo:
                continue
            yield relativo, caminho


def main():
    achados = defaultdict(set)
    for relativo, caminho in arquivos():
        try:
            with open(caminho, encoding='utf-8', errors='ignore') as arquivo:
                texto = arquivo.read()
        except OSError:
            continue
        for nome in PADRAO.findall(texto):
            minusculo = nome.lower()
            if minusculo in RUIDO or len(nome) < 3:
                continue
            achados[minusculo].add(relativo)

    for tabela in sorted(achados):
        arquivos_txt = ', '.join(sorted(achados[tabela]))
        print(f'{tabela:26s} {arquivos_txt}')


if __name__ == '__main__':
    main()
