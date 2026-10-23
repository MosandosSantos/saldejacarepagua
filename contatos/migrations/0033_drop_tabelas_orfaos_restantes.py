"""Remove as ultimas tabelas orfas do legado.

- `scripts`: tabela do app `discador`, removido do projeto. Nao tem model,
  nenhuma consulta SQL a usa e sua FK apontava para `tenants` (as mencoes a
  "scripts" no codigo sao ao pacote Python `scripts/`, nao a tabela).
- `potencia`: tabela legada do GPRB. O cadastro de potencia hoje vive em
  `prefeitura` (e, no Django, em `Vale`/`Membro.potencia`). O unico consumidor
  era o seed de carga `scripts/seed_gprb_loadtest.py`, que ja nao roda porque
  depende de `member`/`loja`/`member_loja`, derrubadas pela 0031.

Em bancos criados do zero pelas migrations essas tabelas nunca existiram, entao
o DROP e idempotente (IF EXISTS).
"""

from django.db import migrations

TABELAS = [
    'scripts',
    'potencia',
]


class Migration(migrations.Migration):

    dependencies = [
        ('contatos', '0032_drop_tabelas_orfaos'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[f'DROP TABLE IF EXISTS "{tabela}" CASCADE;' for tabela in TABELAS],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
