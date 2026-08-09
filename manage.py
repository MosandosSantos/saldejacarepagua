#!/usr/bin/env python
"""Utilitario de linha de comando do Django."""
import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Nao foi possivel importar o Django. Ele esta instalado e "
            "disponivel no PYTHONPATH? Voce esqueceu de ativar o venv?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
