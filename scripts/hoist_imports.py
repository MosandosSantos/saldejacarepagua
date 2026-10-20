#!/usr/bin/env python
"""Sobe imports inline redundantes para o topo do modulo.

Regra `no-inline-imports` (Python Expert Best Practices): todo import fica no
topo do arquivo. Aqui o alvo sao apenas os imports que NAO tem motivo para
ser locais — seja porque o modulo ja importa o mesmo modulo no topo (so falta
o nome), seja porque nao existe ciclo de importacao envolvido.

Casos deliberadamente NAO tocados (import local e legitimo):
  - o modulo importado NAO esta no topo (pode ser ciclo de importacao);
  - o import esta dentro de `try/except ImportError` (dependencia opcional).

Uso:  python scripts/hoist_imports.py [--check]
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

IGNORAR = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", "site-packages",
    "htmlcov", "staticfiles", "tmp", "_legacy", ".pytest_cache", ".ruff_cache",
}


def arquivos(raiz: Path):
    for p in sorted(raiz.rglob("*.py")):
        if any(x in IGNORAR for x in p.parts):
            continue
        yield p


def em_try_import_opcional(node, arvore) -> bool:
    for pai in ast.walk(arvore):
        if isinstance(pai, ast.Try) and node in ast.walk(pai):
            for h in pai.handlers:
                tipos = [t.id for t in ast.walk(h.type) if isinstance(t, ast.Name)] \
                    if h.type else []
                if "ImportError" in tipos or "ModuleNotFoundError" in tipos:
                    return True
    return False


def funcao_ancestral(node, funcoes):
    for f in funcoes:
        if node in ast.walk(f):
            return f
    return None


def spec_alias(alias: ast.alias) -> str:
    """'Usuario as _Usuario' quando ha alias; senao o nome puro."""
    if alias.asname and alias.asname != alias.name:
        return f"{alias.name} as {alias.asname}"
    return alias.name


def render_import(modulo: str, specs: list[str], multilinha: bool) -> str:
    if not multilinha:
        return f"from {modulo} import {', '.join(specs)}\n"
    corpo = "".join(f"    {s},\n" for s in specs)
    return f"from {modulo} import (\n{corpo})\n"


def processar(caminho: Path, escrever: bool):
    fonte = caminho.read_text(encoding="utf-8-sig")
    arvore = ast.parse(fonte)
    linhas = fonte.splitlines(keepends=True)

    # imports de topo por modulo
    topo_por_modulo: dict[str, ast.ImportFrom] = {}
    for node in arvore.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            topo_por_modulo.setdefault(node.module, node)

    funcoes = [n for n in ast.walk(arvore)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

    remocoes: list[tuple[int, int]] = []   # (linha_ini, linha_fim) 1-based, exclusivo
    adicoes: list[tuple[int, str, str]] = []  # (apos_linha, modulo, nomes_csv)

    for node in ast.walk(arvore):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if node in arvore.body:
            continue  # ja e topo
        if em_try_import_opcional(node, arvore):
            continue
        if funcao_ancestral(node, funcoes) is None:
            continue
        topo = topo_por_modulo.get(node.module)
        if topo is None:
            continue  # pode ser ciclo de importacao: deixa como esta
        specs = [spec_alias(a) for a in node.names]
        existentes = {a.asname or a.name for a in topo.names}
        faltando = [a for a in node.names if (a.asname or a.name) not in existentes]
        if not faltando:
            remocoes.append((node.lineno, node.end_lineno))
            continue
        adicoes.append((topo.lineno, node.module, [spec_alias(a) for a in faltando]))
        remocoes.append((node.lineno, node.end_lineno))

    if not adicoes and not remocoes:
        return 0, []

    # ---- monta o texto final ----
    resultado = list(linhas)
    # 1) remocoes (de baixo para cima, para nao invalidar os indices)
    for ini, fim in sorted(remocoes, reverse=True):
        bloco = resultado[ini - 1:fim]
        # remove linhas em branco adjacentes deixadas para tras
        while bloco and bloco[-1].strip() == "":
            bloco.pop()
            fim -= 1
        resultado[ini - 1:fim] = []

    # 2) adicoes aos imports de topo.
    # Todos os nomes destinedos ao MESMO import de topo sao aplicados de uma
    # vez: processar um a um sobrescreve a linha ja corrigida (o segundo
    # `replace` apaga o resultado do primeiro) e o nome some.
    por_no: dict[int, list[str]] = {}
    for apos_linha, modulo, faltando in adicoes:
        por_no.setdefault(id(topo_por_modulo[modulo]), []).extend(faltando)

    # aplica por no de topo, de baixo para cima (mantem os indices validos)
    nos_afetados = []
    for apos_linha, modulo, faltando in adicoes:
        no = topo_por_modulo[modulo]
        if id(no) not in {id(x) for x in nos_afetados}:
            nos_afetados.append(no)

    for no in sorted(nos_afetados, key=lambda n: n.lineno, reverse=True):
        modulo = no.module
        specs = [spec_alias(a) for a in no.names]
        for spec in por_no[id(no)]:
            if spec not in specs:
                specs.append(spec)
        specs.sort(key=lambda s: s.split(" as ")[-1].lower())
        original = ast.get_source_segment(fonte, no) or ""
        multilinha = "(" in original
        ini, fim = no.lineno - 1, no.end_lineno
        # ajuste: remocoes abaixo do no deslocam o no para cima
        ajuste = sum(1 for (i, f) in remocoes if f < no.lineno)
        ini2, fim2 = ini - ajuste, fim - ajuste
        resultado[ini2:fim2] = [render_import(modulo, specs, multilinha)]

    novo = "".join(resultado)
    if novo != fonte:
        if escrever:
            caminho.write_text(novo, encoding="utf-8", newline="")
        return len(remocoes), adicoes
    return 0, []


def main(argv):
    escrever = "--check" not in argv
    caminhos = [a for a in argv[1:] if not a.startswith("-")]
    raiz = Path(caminhos[0]) if caminhos else Path(".")
    total = 0
    for caminho in arquivos(raiz):
        n, adicoes = processar(caminho, escrever)
        if n:
            total += n
            nomes = ", ".join(sorted({a[1] for a in adicoes}))
            print(f"  {caminho.as_posix()}: {n} import(s) subido(s)  [{nomes}]")
    print(f"\nTotal de imports locais removidos: {total}")
    if not escrever:
        print("(modo --check: nada foi gravado)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
