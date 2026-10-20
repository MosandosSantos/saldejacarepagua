#!/usr/bin/env python
"""Verificacao de Python: nomes indefinidos (F821) e redefinicoes (F811).

F821 e o que pega o estrago silencioso de um refactor de import: um
`from X import Y` que some deixa o nome indefinido e so quebra em runtime —
o `manage.py check` passa, porque o nome so e usado dentro de uma funcao.

F401 (import nao usado) sai como informativo: no projeto ha imports
propositais (registro de side-effect, re-export).

Uso:  python scripts/ruff_check.py
"""
from __future__ import annotations

import subprocess
import sys

FATORES = [
    ("F821", "nome indefinido", True),
    ("F811", "redefinicao", True),
    ("F401", "import nao usado", False),
]


def rodar(codigos: str) -> tuple[int, list[str]]:
    r = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--select", codigos,
         "--no-cache", "--output-format=concise", "."],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    linhas = [l for l in r.stdout.splitlines() if l.strip()]
    return r.returncode, linhas


def main() -> int:
    problemas = 0
    for codigo, rotulo, bloqueia in FATORES:
        _, linhas = rodar(codigo)
        print(f"=== {codigo} ({rotulo}) ===")
        if not linhas:
            print("  (nenhum)")
        else:
            for l in linhas[:40]:
                print(f"  {l}")
            if len(linhas) > 40:
                print(f"  ... e mais {len(linhas) - 40}")
            if bloqueia:
                problemas += len(linhas)
        print()
    if problemas:
        print(f"{problemas} problema(s) bloqueante(s).")
        return 1
    print("Nenhum problema bloqueante.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
