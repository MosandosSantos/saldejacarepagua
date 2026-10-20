#!/usr/bin/env python
"""Compara dois relatorios do pytest (formato `-v`) teste a teste.

Uso:  python scripts/compare_test_results.py antes.txt depois.txt
"""
from __future__ import annotations

import re
import sys
from collections import Counter

PADRAO = re.compile(r"::(\S+)\s+(PASSED|FAILED|ERROR|SKIPPED)")


def carregar(caminho: str) -> dict[str, str]:
    resultado: dict[str, str] = {}
    with open(caminho, encoding="utf-8", errors="replace") as f:
        for linha in f:
            m = PADRAO.search(linha)
            if m:
                resultado[m.group(1)] = m.group(2)
    return resultado


def main(argv: list[str]) -> int:
    antes = carregar(argv[1])
    depois = carregar(argv[2])

    print("=" * 62)
    print("COMPARACAO DE RESULTADOS")
    print("=" * 62)
    for nome, dados in (("BASE", antes), ("NOVO", depois)):
        cont = Counter(dados.values())
        print(f"{nome:5} total={len(dados):4}  " +
              "  ".join(f"{k}={v}" for k, v in sorted(cont.items())))

    print()
    mudancas = []
    for nome in antes:
        if nome in depois and depois[nome] != antes[nome]:
            mudancas.append((nome, antes[nome], depois[nome]))
    for nome in depois:
        if nome not in antes:
            mudancas.append((nome, "(ausente)", depois[nome]))

    if not mudancas:
        print("NENHUMA diferenca de status entre os dois relatorios.")
    else:
        print(f"{len(mudancas)} teste(s) com status diferente:")
        for nome, a, b in mudancas:
            marca = "  <-- MELHOROU" if a in ("FAILED", "ERROR") and b == "PASSED" else ""
            if a == "PASSED" and b in ("FAILED", "ERROR"):
                marca = "  <-- REGRESSAO"
            print(f"  {nome}: {a} -> {b}{marca}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
