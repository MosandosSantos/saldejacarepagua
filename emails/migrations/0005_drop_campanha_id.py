"""Idempotência p/ bancos que aplicaram a 0004 antiga (FK emails→campanhas).

A 0004 antiga criava a coluna `campanha_id` e ficava registrada como
aplicada em bancos existentes. Como a 0004 nova nao replica isso, estes
bancos ficariam sem operacao de drop. Esta 0005 executa o mesmo DROP IF
EXISTS: em bancos que ja rodaram a 0004 nova (ou em bancos novos) a coluna
nao existe e o comando e no-op; nos que tinham a FK antiga, a remove.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0004_emailenviado_campanha'),
    ]

    operations = [
        migrations.RunSQL(
            sql='ALTER TABLE emails_enviados DROP COLUMN IF EXISTS "campanha_id"',
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
