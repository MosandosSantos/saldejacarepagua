"""Remove tabelas órfãs dos apps `campanhas` e `discador`.

Os dois apps foram removidos do projeto, mas as tabelas continuavam no banco
herdado, sem nenhum model Django e sem nenhuma consulta SQL no código:

- `campanhas`: só era citada em texto de tela e no nome da rota educativa
  (`/premium/campanhas/`), que não toca o banco;
- `chamadas`: só aparecia como a palavra "chamadas" no código;
- `filas`: nenhuma menção em qualquer arquivo.

Em bancos criados do zero pelas migrations as tabelas nunca existiram, então
o DROP é idempotente (IF EXISTS) e apenas alinha as bases herdadas.
"""

from django.db import migrations

TABELAS = [
    'campanhas',
    'chamadas',
    'filas',
]


class Migration(migrations.Migration):

    dependencies = [
        ('contatos', '0031_drop_tabelas_legadas'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[f'DROP TABLE IF EXISTS "{tabela}" CASCADE;' for tabela in TABELAS],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
