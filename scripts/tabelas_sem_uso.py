"""Aponta tabelas do banco que nenhum codigo do projeto usa.

Criterios:
  - TABELA SEM MODEL: nao existe model Django para ela. Pode ser:
      * "usada por SQL cru" -> algum arquivo executa consulta nela;
      * "mortas"            -> nenhum arquivo de codigo executa SQL nela;
  - MODEL SEM USO: existe model, mas nenhum arquivo fora da definicao e das
    migrations cita a classe, o db_table ou o related_name.

Uso: python scripts/tabelas_sem_uso.py
"""

import os
import re
import sys
from collections import defaultdict

import django

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.apps import apps  # noqa: E402
from django.conf import settings  # noqa: E402
from django.db import connection  # noqa: E402

# Pastas que nao sao codigo do projeto (skills, caches, artefatos).
IGNORAR_DIR = {
    '.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache',
    '.mypy_cache', '.ruff_cache', 'staticfiles', 'media', 'logs', 'htmlcov',
    '.agents', '.github', '.opencode', '.claude', '.codex', '.specify',
    '.playwright-mcp', '.freebuff', '.impeccable', 'theme',
}
SUFIXOS = {'.py', '.html', '.js'}

SQL_USO = re.compile(
    r'\b(?:from|join|into|update|table|exists)\s+["\'`]?{tabela}\b',
    re.IGNORECASE,
)


def arquivos_de_codigo():
    for pasta, subpastas, arquivos in os.walk(RAIZ):
        subpastas[:] = [s for s in subpastas if s not in IGNORAR_DIR]
        for arquivo in arquivos:
            if os.path.splitext(arquivo)[1] not in SUFIXOS:
                continue
            caminho = os.path.join(pasta, arquivo)
            relativo = os.path.relpath(caminho, RAIZ).replace(os.sep, '/')
            if '/migrations/' in relativo:
                continue
            yield relativo, caminho


def linhas_com(termo, arquivos, ignorar_definicao=''):
    """Devolve (arquivos, exemplos) de linhas que citam o termo."""
    palavra = re.compile(rf'\b{re.escape(termo)}\b')
    achados = []
    for relativo, caminho in arquivos:
        if relativo == ignorar_definicao:
            continue
        try:
            with open(caminho, encoding='utf-8', errors='ignore') as arquivo:
                for numero, linha in enumerate(arquivo, 1):
                    if palavra.search(linha):
                        achados.append((relativo, numero, linha.strip()))
        except OSError:
            continue
    arquivos_unicos = sorted({local for local, _, _ in achados})
    return arquivos_unicos, achados


def sql_real(tabela, achados):
    padrao = re.compile(SQL_USO.pattern.format(tabela=re.escape(tabela)), re.IGNORECASE)
    return [item for item in achados if padrao.search(item[2])]


config = settings.DATABASES['default']
print('BANCO LIDO PELO DJANGO')
print(f"  host={config.get('HOST')} porta={config.get('PORT')} "
      f"banco={config.get('NAME')} usuario={config.get('USER')}")
with connection.cursor() as cursor:
    cursor.execute('select version()')
    print(f"  servidor: {cursor.fetchone()[0][:60]}")
    cursor.execute("select tablename from pg_tables where schemaname = 'public'")
    tabelas = {linha[0] for linha in cursor.fetchall()}

arquivos = list(arquivos_de_codigo())
models = [m for m in apps.get_models(include_auto_created=True) if m._meta.managed]
por_tabela = {m._meta.db_table: m for m in models}

print(f'\narquivos de codigo analisados: {len(arquivos)}')
print(f'tabelas no banco: {len(tabelas)} | models: {len(models)}')

print('\n' + '=' * 74)
print('1) TABELAS SEM MODEL DJANGO')
print('=' * 74)
mortas, por_sql = [], []
for tabela in sorted(tabelas - set(por_tabela)):
    _, achados = linhas_com(tabela, arquivos)
    usos = sql_real(tabela, achados)
    if usos:
        por_sql.append((tabela, usos))
    else:
        mortas.append((tabela, achados))

print(f'\n-- 1a) SEM SQL NENHUM: CANDIDATAS A EXCLUSAO ({len(mortas)})')
for tabela, achados in mortas:
    print(f'   {tabela:24s} ({len(achados)} mencao(oes) textual(is))')
    for local, numero, linha in achados[:3]:
        print(f'        {local}:{numero}  {linha[:90]}')

print(f'\n-- 1b) SEM MODEL, MAS USADAS POR SQL CRU: MANTER ({len(por_sql)})')
for tabela, usos in por_sql:
    print(f'   {tabela:24s} {len(usos)} consulta(s)')
    for local, numero, linha in usos[:2]:
        print(f'        {local}:{numero}  {linha[:90]}')

print('\n' + '=' * 74)
print('2) MODELS QUE NENHUM ARQUIVO CITA (nem classe, nem tabela, nem related_name)')
print('=' * 74)
orfaos = []
for model in sorted(models, key=lambda m: (m._meta.app_label, m.__name__)):
    if model._meta.app_label.startswith('django.') or model._meta.auto_created:
        continue
    modulo = model.__module__.replace('.', '/') + '.py'
    definicao = os.path.relpath(modulo, RAIZ).replace(os.sep, '/')
    termos = [model.__name__, model._meta.db_table]
    for relacao in model._meta.related_objects:
        for termo in (getattr(relacao, 'related_query_name', None), ):
            if callable(termo):
                termo = termo()
            if termo:
                termos.append(termo)
        acessor = relacao.get_accessor_name()
        if acessor:
            termos.append(acessor)
    citado = False
    for termo in termos:
        if not termo:
            continue
        _, achados = linhas_com(termo, arquivos, definicao)
        if achados:
            citado = True
            break
    if not citado:
        orfaos.append((model._meta.app_label, model.__name__, model._meta.db_table))

if not orfaos:
    print('  nenhum: todo model aparece em algum arquivo de codigo')
for app, classe, tabela in orfaos:
    print(f'  {app + "." + classe:38s} tabela {tabela}')

print('\n' + '=' * 74)
print('3) TABELAS COM MODEL E SEM USO NO CODIGO')
print('=' * 74)
if not orfaos:
    print('  nenhuma')
else:
    print('  ' + ', '.join(tabela for _, _, tabela in orfaos))
