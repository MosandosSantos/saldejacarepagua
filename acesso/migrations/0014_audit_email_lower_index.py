"""Auditoria DB — índice funcional LOWER(email) em usuarios.

O login usa `filter(email__iexact=email)` (em acesso/views.py e na API).
`unique=True` cria um índice B-tree comum, mas `__iexact` aplica UPPER()
e **não** usa esse índice → full table scan no login. Este índice funcional
resolve o problema no PostgreSQL (case-insensitive).
"""
from django.db import migrations, models
from django.db.models.functions import Lower


class Migration(migrations.Migration):

    dependencies = [
        ('acesso', '0013_drop_acordos_tables'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='usuario',
            index=models.Index(Lower('email'), name='usuario_email_lower_idx'),
        ),
    ]
