"""Remove a coluna `campanha_id` do banco (app campanhas excluido do projeto).

O app campanhas nao existe mais; a FK emails→campanhas.Campanha foi removida
dos models. Operacao apenas de banco (RunSQL nao toca no estado dos models —
que nunca devem ter tido o campo em bancos novos). `IF EXISTS` torna a
operacao segura tanto para bancos que tinham a coluna quanto para novos.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0003_emailenviado_cliques_convertido_em'),
    ]

    operations = [
        migrations.RunSQL(
            sql='ALTER TABLE emails_enviados DROP COLUMN IF EXISTS "campanha_id"',
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
