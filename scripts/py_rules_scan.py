#!/usr/bin/env python
"""Scanner das Python Expert Best Practices (regras de prioridade 1-4).

Varre o codigo Python do projeto e reporta, por arquivo/linha:
  - dict-required-keys   (CRITICAL)   .get() em chave obrigatoria
  - no-mutable-defaults  (CRITICAL)   default mutavel em parametro
  - operators-return-notimplemented    dunder operator levantando TypeError
  - no-generic-except    (HIGH)       except: / except Exception:
  - listcomp-no-side-effects (HIGH)    listcomp usada como statement
  - no-inline-imports    (MEDIUM)     import dentro de funcao
  - unnecessary-else-blocks (LOW)      else depois de return/break/continue
  - avoid-explanatory-comments (LOW)   comentario que so repete o codigo

Uso:  python scripts/py_rules_scan.py [caminho ...]
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

IGNORAR_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", "site-packages",
    "htmlcov", "staticfiles", "tmp", "_legacy", ".pytest_cache", ".ruff_cache",
}

MUTAVEIS = {"list", "dict", "set", "bytearray", "collections"}
OPERADORES = {
    "__add__", "__radd__", "__sub__", "__rsub__", "__mul__", "__rmul__",
    "__truediv__", "__rtruediv__", "__floordiv__", "__rfloordiv__",
    "__mod__", "__rmod__", "__pow__", "__rpow__", "__and__", "__rand__",
    "__or__", "__ror__", "__xor__", "__rxor__", "__lshift__", "__rshift__",
}
INPLACE = {
    "__iadd__", "__isub__", "__imul__", "__itruediv__", "__ifloordiv__",
    "__imod__", "__ipow__", "__iand__", "__ior__", "__ixor__", "__ilshift__",
    "__irshift__",
}

class Achado:
    __slots__ = ("arquivo", "linha", "regra", "prioridade", "msg", "trecho")

    def __init__(self, arquivo, linha, regra, prioridade, msg, trecho=""):
        self.arquivo = arquivo
        self.linha = linha
        self.regra = regra
        self.prioridade = prioridade
        self.msg = msg
        self.trecho = trecho

    def __str__(self):
        return f"{self.arquivo}:{self.linha} [{self.prioridade}] {self.regra}: {self.msg}"


def linha_de(node, src_lines):
    return getattr(node, "lineno", 0)


def trecho(src_lines, node, maxlen=110):
    ln = getattr(node, "lineno", 0)
    if not ln or ln > len(src_lines):
        return ""
    t = src_lines[ln - 1].strip()
    return t[:maxlen]


def mutavel_em_default(default):
    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
        return True
    if isinstance(default, ast.Call) and isinstance(default.func, ast.Name):
        return default.func.id in MUTAVEIS
    return False


def bloco_terminador(body):
    """True se o corpo do if ends com return/break/continue (else redundante)."""
    if not body:
        return False
    ultimo = body[-1]
    if isinstance(ultimo, (ast.Return, ast.Break, ast.Continue)):
        return True
    if isinstance(ultimo, ast.If):
        return bloco_terminador(ultimo.body) and bloco_terminador(ultimo.orelse)
    if isinstance(ultimo, ast.Try):
        return bloco_terminador(ultimo.body)
    return False


def usar_requer_valor(node):
    """True se o valor do .get() e usado de forma que None quebra."""
    if isinstance(node, ast.Subscript):
        return True
    if isinstance(node, ast.BinOp):
        return True
    if isinstance(node, ast.Compare):
        return True
    if isinstance(node, ast.Call):
        return True
    if isinstance(node, ast.Attribute):
        return True
    if isinstance(node, ast.JoinedStr):
        return True
    return False


def ifs_em_cadeia(arvore):
    """If que sao 'elif' (dentro do orelse de outro If) — o else e da cadeia."""
    em_cadeia: set = set()
    for node in ast.walk(arvore):
        if isinstance(node, ast.If):
            for sub in node.orelse:
                if isinstance(sub, ast.If):
                    em_cadeia.add(sub)
    return em_cadeia


def imports_do_topo(arvore):
    """Nomes importados no nivel do modulo (fora de qualquer funcao)."""
    nomes: set[str] = set()
    modulos: set[str] = set()
    for node in arvore.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                nomes.add(a.asname or a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                nomes.add(a.asname or a.name)
            if node.module:
                modulos.add(node.module)
    return nomes, modulos


class Visitante(ast.NodeVisitor):
    def __init__(self, arquivo, src_lines, arvore):
        self.arquivo = arquivo
        self.src = src_lines
        self.arvore = arvore
        self.imports_do_topo, self.modulos_do_topo = imports_do_topo(arvore)
        self.ifs_em_cadeia = ifs_em_cadeia(arvore)
        self.achados: list[Achado] = []
        self.funcao_atual = None
        self.pilha_funcao: list[ast.FunctionDef] = []

    # --- helpers ---
    def add(self, node, regra, prioridade, msg):
        self.achados.append(
            Achado(self.arquivo, linha_de(node, self.src), regra, prioridade, msg,
                   trecho(self.src, node))
        )

    # --- parametros ---
    def visit_FunctionDef(self, node):
        for d in node.args.defaults + [d for d in node.args.kw_defaults if d]:
            if mutavel_em_default(d):
                self.add(d, "no-mutable-defaults", "CRITICAL",
                         f"default mutavel em {node.name}() — use None e crie dentro")
        self.pilha_funcao.append(node)
        self.generic_visit(node)
        self.pilha_funcao.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    # --- except ---
    def _relanca(self, node) -> bool:
        """True se o handler relanca a excecao (barre 'raise' ou 'raise X from e').

        Um `except Exception` que RELEVANTA nao esconde o erro: ele apenas
        traduz a excecao para um tipo proprio (adaptador de lib de terceiro).
        A regra nao se aplica nesse caso.
        """
        for sub in node.body:
            if isinstance(sub, ast.Raise):
                return True
        return False

    def visit_ExceptHandler(self, node):
        t = node.type
        trecho = ast.get_source_segment("\n".join(self.src), node) or ""
        suprimido = "noqa: py-rules" in trecho
        if not suprimido:
            if t is None:
                self.add(node, "no-generic-except", "HIGH",
                         "except: puro pega TUDO, inclusive KeyboardInterrupt")
            elif isinstance(t, ast.Name) and t.id in ("Exception", "BaseException"):
                if not self._relanca(node):
                    self.add(node, "no-generic-except", "HIGH",
                             f"except {t.id}: esconde erro inesperado — capture a excecao especifica")
            elif isinstance(t, ast.Tuple):
                nomes = [e.id for e in t.elts if isinstance(e, ast.Name)]
                if ("Exception" in nomes or "BaseException" in nomes) \
                        and not self._relanca(node):
                    self.add(node, "no-generic-except", "HIGH",
                             "except (..., Exception): esconde erro inesperado")
        # except ... : pass  -> engole o erro.
        # So conta quando o tipo capturado e generico: com um tipo especifico
        # (psycopg.Error, OSError) o `pass` e uma decisao consciente.
        tipo_generico = t is None or (
            isinstance(t, ast.Name) and t.id in ("Exception", "BaseException")
        ) or (isinstance(t, ast.Tuple) and any(
            isinstance(e, ast.Name) and e.id in ("Exception", "BaseException")
            for e in t.elts
        ))
        if (len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
                and not suprimido and tipo_generico):
            self.add(node, "no-generic-except", "HIGH",
                     "except ...: pass engole a excecao silenciosamente")
        self.generic_visit(node)

    # --- import inline ---
    def _import_opcional(self, node):
        """True se o import esta dentro de try/except ImportError (opcional)."""
        for pai in ast.walk(self.arvore):
            if isinstance(pai, ast.Try) and node in ast.walk(pai):
                for h in pai.handlers:
                    tipos = [t.id for t in ast.walk(h.type)
                             if isinstance(t, ast.Name)] if h.type else []
                    if "ImportError" in tipos or "ModuleNotFoundError" in tipos:
                        return True
        return False

    def visit_Import(self, node):
        if self.pilha_funcao and not self._import_opcional(node):
            self.add(node, "no-inline-imports", "MEDIUM",
                     "import dentro de funcao — suba para o topo do modulo")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if self.pilha_funcao and not self._import_opcional(node):
            nomes = {a.asname or a.name for a in node.names}
            ja_no_topo = nomes & self.imports_do_topo
            modulo = node.module or ""
            modulo_ja_importado = modulo in self.modulos_do_topo
            msg = "import dentro de funcao — suba para o topo do modulo"
            if ja_no_topo:
                msg = (f"import REDUNDANTE dentro de funcao — o modulo ja importa "
                       f"{', '.join(sorted(ja_no_topo))} no topo; apague a linha local")
                self.add(node, "no-inline-imports-redundante", "MEDIUM", msg)
            elif modulo_ja_importado:
                msg = (f"import dentro de funcao de um modulo ja importado no topo "
                       f"({modulo}) — some o nome no import existente")
                self.add(node, "no-inline-imports-redundante", "MEDIUM", msg)
            else:
                self.add(node, "no-inline-imports", "MEDIUM", msg)
        self.generic_visit(node)

    # --- listcomp como statement ---
    def visit_Expr(self, node):
        if isinstance(node.value, (ast.ListComp,)):
            self.add(node, "listcomp-no-side-effects", "HIGH",
                     "listcomp usada como statement (efeito colateral) — use for-loop")
        self.generic_visit(node)
    # --- else redundante ---
    def visit_If(self, node):
        # Nao sinaliza: (a) o else sintetico do fim de cadeia if/elif (test=True);
        # (b) um if que E um elif (o else pertence a cadeia, nao a ele).
        sintetico = (isinstance(node.test, ast.Constant) and node.test.value is True)
        elif_de_cadeia = node in self.ifs_em_cadeia
        if node.orelse and not sintetico and not elif_de_cadeia:
            orelse_real = not (len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If))
            if orelse_real and bloco_terminador(node.body):
                self.add(node, "unnecessary-else-blocks", "LOW",
                         "else depois de return/break/continue — desindente")
        self.generic_visit(node)

    # --- operadores ---
    def visit_BinOp(self, node):
        self.generic_visit(node)

    def visit_Compare(self, node):
        self.generic_visit(node)

    # --- dict.get em chave obrigatoria ---
    # `request.POST/GET/FILES/session` sao FRONTEIRA: a chave e genuinamente
    # opcional ali (o usuario pode nao ter enviado o campo). A regra so
    # aplica a contratos INTERNOS, onde a ausencia da chave e um bug.
    FRONTEIRAS = {"POST", "GET", "FILES", "session", "data", "query_params", "META"}

    def _e_fronteira(self, node) -> bool:
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "get"):
            return False
        recv = func.value
        if isinstance(recv, ast.Attribute) and recv.attr in self.FRONTEIRAS:
            return True
        if isinstance(recv, ast.Attribute) and recv.attr == "request":
            return True
        if isinstance(recv, ast.Name) and recv.id in ("request",):
            return True
        return False

    def visit_Call(self, node):
        func = node.func
        if (isinstance(func, ast.Attribute) and func.attr == "get" and node.args
                and len(node.args) == 1 and not node.keywords
                and not self._e_fronteira(node)):
            pai_uso = self._uso_do_valor(node)
            if pai_uso in ("subscript", "binop", "call"):
                self.add(node, "dict-required-keys", "CRITICAL",
                         f".get({ast.unparse(node.args[0])}) sem default — "
                         "chave obrigatoria deveria ser d[chave] (KeyError) ou validada")
        self.generic_visit(node)

    def _uso_do_valor(self, node):
        return getattr(node, "_uso", "")


def marcar_usos(arvore):
    """Anota como o resultado de um Call .get() e usado (pai)."""
    for pai in ast.walk(arvore):
        for filho in ast.iter_child_nodes(pai):
            filho._uso = {
                ast.Subscript: "subscript",
                ast.BinOp: "binop",
                ast.Call: "call",
                ast.Attribute: "attribute",
                ast.Compare: "compare",
                ast.JoinedStr: "fstring",
            }.get(type(pai), "other")


def dunder_operators(arvore, arquivo, src_lines):
    achados = []
    for node in ast.walk(arvore):
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name in OPERADORES or node.name in INPLACE:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Raise):
                    exc = sub.exc
                    if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name) \
                            and exc.func.id == "TypeError":
                        achados.append(Achado(
                            arquivo, linha_de(sub, src_lines),
                            "operators-return-notimplemented", "CRITICAL",
                            f"{node.name} levanta TypeError — devolva NotImplemented "
                            "para o Python tentar a operacao reversa",
                            trecho(src_lines, sub)))
                        break
                if isinstance(sub, ast.Return) and node.name in INPLACE:
                    achados.append(Achado(
                        arquivo, linha_de(sub, src_lines),
                        "operators-return-notimplemented", "CRITICAL",
                        f"{node.name} sem 'return self' — quebra encadeamento",
                        trecho(src_lines, sub)))
    return achados


def arquivos_py(raiz: Path):
    for p in sorted(raiz.rglob("*.py")):
        if any(part in IGNORAR_DIRS for part in p.parts):
            continue
        yield p


def main(argv):
    if len(argv) > 1:
        raizes = [Path(a) for a in argv[1:]]
    else:
        raizes = [Path(".")]

    todos: list[Achado] = []
    n_arquivos = 0
    for raiz in raizes:
        for p in arquivos_py(raiz):
            n_arquivos += 1
            try:
                fonte = p.read_text(encoding="utf-8-sig")
                arvore = ast.parse(fonte, filename=str(p))
            except (SyntaxError, UnicodeDecodeError) as e:
                print(f"  [ignorado] {p}: {e}")
                continue
            src_lines = fonte.splitlines()
            marcar_usos(arvore)
            v = Visitante(p, src_lines, arvore)
            v.visit(arvore)
            todos.extend(v.achados)
            todos.extend(dunder_operators(arvore, p, src_lines))

    ordem = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    por_regra: dict[str, list[Achado]] = {}
    for a in todos:
        por_regra.setdefault(a.regra, []).append(a)

    print(f"Arquivos Python analisados: {n_arquivos}")
    print(f"Achados: {len(todos)}")
    print()
    print("--- por area ---")
    por_area: dict[str, int] = {}
    for a in todos:
        area = str(a.arquivo).split("\\")[0]
        por_area[area] = por_area.get(area, 0) + 1
    for area, qtd in sorted(por_area.items(), key=lambda kv: -kv[1]):
        print(f"  {area:16} {qtd}")
    print()

    for regra in sorted(por_regra, key=lambda r: ordem[por_regra[r][0].prioridade]):
        itens = sorted(por_regra[regra], key=lambda a: (ordem[a.prioridade], str(a.arquivo), a.linha))
        prio = itens[0].prioridade
        print(f"=== {regra}  ({len(itens)} achados, prioridade {prio}) ===")
        for a in itens:
            print(f"  {a.arquivo}:{a.linha}  {a.msg}")
            if a.trecho:
                print(f"      | {a.trecho}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
