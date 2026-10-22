"""Compara as tabelas declaradas nos models com as que existem no banco atual.

Rode no ambiente que aponta para o banco alvo:

    python scripts/diagnostico_schema.py            # local (usa .env)
    docker compose exec -T app python scripts/diagnostico_schema.py   # container

Saida:
    faltando     -> tabelas que os models esperam e nao existem (rode `migrate`)
    sem model    -> tabelas no banco sem model correspondente (legado/drift)
"""

import os
import sys

import django

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.apps import apps
from django.db import connection

# Tabelas do proprio Django que nao tem model (o recorder de migrations).
TABELAS_DJANGO = {'django_migrations'}

esperadas = {
    model._meta.db_table
    for model in apps.get_models(include_auto_created=True)
    if model._meta.managed
} | TABELAS_DJANGO

with connection.cursor() as cursor:
    cursor.execute("select tablename from pg_tables where schemaname = 'public'")
    existentes = {linha[0] for linha in cursor.fetchall()}

faltando = sorted(esperadas - existentes)
sobrando = sorted(existentes - esperadas)

print(f'tabelas nos models: {len(esperadas)}')
print(f'tabelas no banco:   {len(existentes)}')
print(f'faltando no banco:  {faltando or "nenhuma"}')
print(f'sem model (legado): {sobrando or "nenhuma"}')

if faltando:
    raise SystemExit(1)
