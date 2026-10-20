#!/ coding: utf-8 -*-
"""Compara o conjunto de nomes importados entre dois estados do projeto.

Detecta perda de nome durante um refactor de imports: um `from X import Y`
que existia antes e sumiu depois quebra o codigo em runtime (so aparece
quando o nome e usado — o `import` em si nao falha).

Uso:  python scripts/check_import_regression.py <ref-git> [dir]
       (sem <ref-git>, compara o worktree contra o indice)
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

IGNORAR_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", "site-packages",
    "htmlcov", "staticfiles", "tmp", "_legacy", ".pytest_cache", ".ruff_cache",
}


def nomes_importados(arvore: ast.AST) -> set[tuple[str, str]]:
    """Conjunto (modulo, nome) de tudo que o arquivo importa, em qualquer nivel."""
    nomes: set[tuple[str, str]] = set()
    for node in ast.walk(arvore):
        if isinstance(node, ast.Import):
            for a in node.names:
                nomes.add(("", a.name))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for a in node.names:
                nomes.add((mod, a.name))
    return nomes


def arquivos(raiz: Path):
    for p in sorted(raiz.rglob("*.py")):
        if any(x in IGNORAR_DIRS for x in p.parts):
            continue
        yield p


def main(argv: list[str]) -> int:
    ref = argv[1] if len(argv) > 1 else "HEAD"
    raiz = Path(argv[2]) if len(argv) > 2 else Path(".")

    perdidos: list[tuple[str, str, str]] = []
    novos: list[tuple[str, str, str]] = []
    comparados = 0

    for p in arquivos(raiz):
        rel = p.as_posix()
        atual = p.read_text(encoding="utf-8-sig")
        try:
            nomes_antes = nomes_importados(ast.parse(atual))
        except SyntaxError:
            continue
        r = subprocess.run(["git", "show", f"{ref}:{rel}"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0 or not r.stdout:
            continue
        try:
            nomes_ref = nomes_importados(ast.parse(r.stdout))
        except SyntaxError:
            continue
        comparados += 1
        for mod, nome in sorted(nomes_ref - nomes_antes):
            perdidos.append((rel, mod, nome))
        for mod, nome in sorted(nomes_antes - nomes_ref):
            novos.append((rel, mod, nome))

    print(f"Arquivos comparados com {ref}: {comparados}")
    print(f"\nNOMES PERDIDOS (existed no ref, sumiram agora): {len(perdidos)}")
    for rel, mod, nome in perdidos:
        print(f"  {rel}: {mod or '.'}.{nome}")
    print(f"\nNomes novos (apareceram agora): {len(novos)}")
    for rel, mod, nome in novos[:40]:
        print(f"  {rel}: {mod or '.'}.{nome}")
    if len(novos) > 40:
        print(f"  ... e mais {len(novos) - 40}")
    return 1 if perdidos else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
