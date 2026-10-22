"""Remove tabelas legadas duplicadas e as tabelas do app Gestão.

Tabelas legadas (esquema Prisma antigo), sem model Django:
`loja`, `member`, `member_loja` e `rito` (singular). As equivalentes atuais
são `lojas`, `membros`, `membros_lojas` e `ritos`.

Tabelas do app `gestao` (GEOD-CEOD), removido do projeto: as seis tabelas
`gestao_*` deixam de existir junto com o código que as usava.
"""

from django.db import migrations

TABELAS = [
    # Legadas (duplicadas)
    'member_loja',
    'member',
    'loja',
    'rito',
    # App Gestão removido
    'gestao_pagamento',
    'gestao_congressista',
    'gestao_inscricao',
    'gestao_tipo_inscricao',
    'gestao_capitulo',
    'gestao_campanha',
]


class Migration(migrations.Migration):

    dependencies = [
        ('contatos', '0030_rito_global'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[f'DROP TABLE IF EXISTS "{tabela}" CASCADE;' for tabela in TABELAS],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
