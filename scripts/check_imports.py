#!/usr/bin/env python
"""Importa todos os modulos Python do projeto e reporta falhas.

Pega breakage de import (alias perdido, nome inexistente no modulo) que o
`manage.py check` nao alcanca — o check so importa o que a configuracao
registra.

Uso:  python scripts/check_imports.py
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

IGNORAR_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", "site-packages",
    "htmlcov", "staticfiles", "tmp", "_legacy", ".pytest_cache", ".ruff_cache",
    "scripts", "probe_usuarios.py",
}
IGNORAR_ARQUIVOS = {"manage.py", "probe_usuarios.py", "probe_capitulo.py"}


def modulos():
    raiz = Path(".")
    for p in sorted(raiz.rglob("*.py")):
        partes = set(p.parts)
        if partes & IGNORAR_DIRS:
            continue
        if p.name in IGNORAR_ARQUIVOS:
            continue
        if p.name.startswith("_") and len(p.parts) == 1:
            continue
        if p.name == "__init__.py":
            continue
        yield p


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    sys.path.insert(0, str(Path.cwd()))
    import django

    django.setup()

    ok = 0
    falhas: list[tuple[str, str]] = []
    for p in modulos():
        mod = ".".join(p.with_suffix("").parts)
        try:
            importlib.import_module(mod)
            ok += 1
        except Exception as e:  # noqa: py-rules
            falhas.append((mod, f"{type(e).__name__}: {e}"))

    print(f"Modulos importados com sucesso: {ok}")
    print(f"Falhas: {len(falhas)}")
    for mod, err in falhas:
        print(f"  {mod}\n      {err}")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
