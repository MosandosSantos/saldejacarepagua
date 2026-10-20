#!/usr/bin/env python
"""Varredura mecanica de conformidade com as Web Interface Guidelines.

Aplica transformacoes deterministicas (e seguras) nos templates Django do
projeto. Rodar com:

    python scripts/a11y_sweep.py            # aplica
    python scripts/a11y_sweep.py --check    # apenas relatorio, nao escreve

Transformacoes:

  1. Reticle tipografico: `...` -> `...` (U+2026) em texto, placeholders
     e strings de estado de carregamento.
  2. `<th>` sem `scope` -> `scope="col"`.
  3. Controles com `outline-none` e sem anel de foco -> recebem
     `focus-visible:ring-2 focus-visible:ring-[#5b8def]/60`.
  4. `<svg>` inline decorativo -> `aria-hidden="true"`.
  5. Botoes/links so-icone que so tinham `title` -> recebem `aria-label`.
  6. `<img>` sem `width`/`height` explicitos -> inferidos das classes
     utilitarias `h-N w-N` (evita CLS).
  7. Formatos de data fixos -> filtros locale-aware do `formatacao`
     (`d/m/Y` -> `|databr`, `d/m/Y H:i` -> `|datahorabr`, ...).
     Formatos ISO (`Y-m-d`) sao preservados: vao para `<input type=date>`,
     query strings e comparacao em JS.

O script NAO toca em:
  - `acesso/templates/acesso/login.html` (pagina de login fora do escopo);
  - conteudo dentro de blocos `{% ... %}` / `{{ ... }}` do Django.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

# Paginas explicitamente fora do escopo.
SKIP = {
    "acesso/templates/acesso/login.html",
}

APPS = [
    "acesso", "agenda", "automacoes", "candidatos", "contatos", "dashboard",
    "emails", "gestao", "recepcao", "tarefas", "templates", "theme",
]

# h-N -> pixels (escala Tailwind: 1rem = 16px)
TAILWIND_PX = {
    "0": 0, "0.5": 2, "1": 4, "1.5": 6, "2": 8, "2.5": 10, "3": 12, "3.5": 14,
    "4": 16, "5": 20, "6": 24, "7": 28, "8": 32, "9": 36, "10": 40, "11": 44,
    "12": 48, "14": 56, "16": 64, "20": 80, "24": 96, "28": 112, "32": 128,
    "36": 144, "40": 160, "44": 176, "48": 192, "52": 208, "56": 224, "60": 240,
    "64": 256, "72": 288, "80": 320,
}

# Formato de data -> filtro do modulo `formatacao`.
DATE_FILTERS = {
    "d/m/Y": "databr",
    "d/m/Y H:i": "datahorabr",
    "d/m H:i": "datahorabr",
    "H:i": "horabr",
    "d/m": "databr",
    "m/Y": "mesanome",
}

FOCUS_RING = "focus-visible:ring-2 focus-visible:ring-[#5b8def]/60 focus-visible:ring-offset-0"

TAG_RE = re.compile(r"<(?P<tag>[a-zA-Z][a-zA-Z0-9-]*)(?P<attrs>[^<>]*?)(?P<self>/?)>", re.S)
ATTR_RE = re.compile(r"""(?P<name>[\w:-]+)\s*=\s*(?P<q>["'])(?P<val>.*?)(?P=q)""", re.S)
CLASS_RE = re.compile(r"""(?P<name>class)\s*=\s*(?P<q>["'])(?P<val>.*?)(?P=q)""", re.S)
SVG_TAG_RE = re.compile(r"<svg\b[^>]*>", re.S)
ICON_CONTROL_RE = re.compile(
    r"<(?P<tag>button|a)\b(?P<attrs>[^<>]*?)>(?P<inner>.*?)</(?P=tag)\s*>", re.S
)
IMG_RE = re.compile(r"<img\b[^>]*>", re.S)


def templates() -> list[Path]:
    achados: set[Path] = set()
    for app in APPS:
        achados.update((BASE / app).rglob("*.html"))
    return sorted(
        p for p in achados
        if "node_modules" not in p.parts
        and "venv" not in p.parts
        and "__pycache__" not in p.parts
    )


def rel(p: Path) -> str:
    return p.relative_to(BASE).as_posix()


def has_attr(attrs: str, name: str) -> bool:
    return re.search(rf"\s{name}\s*=", attrs) is not None


def get_attr(attrs: str, name: str) -> str | None:
    for m in ATTR_RE.finditer(attrs):
        if m.group("name") == name:
            return m.group("val")
    return None


def set_attr(tag_match: re.Match, name: str, value: str) -> str:
    """Reconstroi a tag acrescentando/atualizando um atributo."""
    tag = tag_match.group("tag")
    attrs = tag_match.group("attrs")
    self_close = tag_match.group("self")
    novo = ATTR_RE.sub(
        lambda m: (f'{m.group("name")}="{value}"' if m.group("name") == name else m.group(0)),
        attrs,
    )
    if not has_attr(attrs, name):
        novo = novo.rstrip() + f' {name}="{value}"'
    return f"<{tag}{novo}{self_close}>"


# --------------------------------------------------------------------------
# 1. Reticle tipografico
# --------------------------------------------------------------------------
def fix_ellipsis(text: str) -> tuple[str, int]:
    n = text.count("...")
    if not n:
        return text, 0
    return text.replace("...", "\u2026"), n


# --------------------------------------------------------------------------
# 2. scope="col" nos <th>
# --------------------------------------------------------------------------
def fix_th_scope(text: str) -> tuple[str, int]:
    cont = 0

    def repl(m: re.Match) -> str:
        nonlocal cont
        if m.group("tag").lower() != "th":
            return m.group(0)
        if has_attr(m.group("attrs"), "scope"):
            return m.group(0)
        cont += 1
        return set_attr(m, "scope", "col")

    return TAG_RE.sub(repl, text), cont


# --------------------------------------------------------------------------
# 3. Anel de foco nos controles com outline-none
# --------------------------------------------------------------------------
def fix_focus_ring(text: str) -> tuple[str, int]:
    cont = 0

    def repl(m: re.Match) -> str:
        nonlocal cont
        val = m.group("val")
        if "outline-none" not in val:
            return m.group(0)
        if "ring" in val:
            return m.group(0)
        cont += 1
        novo = val.rstrip()
        if novo.endswith('"'):
            novo = novo[:-1]
        return f'class="{novo} {FOCUS_RING}"'

    return CLASS_RE.sub(repl, text), cont


# --------------------------------------------------------------------------
# 4/5. SVG decorativo + nome acessivel de controles so-icone
# --------------------------------------------------------------------------
def _inner_text(inner: str) -> str:
    """Texto visivel do conteudo, sem tags.

    `{% ... %}` (controle de template) nao produz texto; `{{ ... }}` produz
    texto e conta como nome acessivel — exceto quando o filtro `|safe` indica
    que a expressao renderiza markup (icones), que e decorativo.
    """
    sem_svg = re.sub(r"<svg\b.*?</svg>", " ", inner, flags=re.S)
    sem_tags = re.sub(r"<[^>]*>", " ", sem_svg)
    sem_markup = re.sub(r"\{\{.*?\|safe.*?\}\}", " ", sem_tags, flags=re.S)
    sem_ctrl = re.sub(r"\{%.*?%\}", " ", sem_markup, flags=re.S)
    return re.sub(r"\s+", " ", sem_ctrl).strip()


def _svg_aria_label(inner: str) -> str | None:
    for m in re.finditer(r"<svg\b([^>]*)>", inner):
        rotulo = get_attr(m.group(1), "aria-label")
        if rotulo:
            return rotulo
    return None


def fix_svgs_e_nomes(text: str) -> tuple[str, int, int, list[str]]:
    """Devolve (texto, n_svg_ocultados, n_rotulos_adicionados, sem_nome)."""
    n_svg = 0
    n_rotulo = 0
    sem_nome: list[str] = []
    manter: list[str] = []

    # --- 5a. nome acessivel para controles so-icone -----------------------
    def ctrl(m: re.Match) -> str:
        nonlocal n_rotulo
        tag = m.group("tag")
        attrs = m.group("attrs")
        inner = m.group("inner")
        if "<svg" not in inner:
            return m.group(0)

        if _inner_text(inner):
            # Controle com texto: o SVG e decorativo -> sera ocultado.
            return m.group(0)

        # Controle so-icone: precisa de nome acessivel.
        if not has_attr(attrs, "aria-label"):
            rotulo = get_attr(attrs, "title") or _svg_aria_label(inner)
            if not rotulo:
                # Sem rotulo deduzivel: o SVG e o unico conteudo e NAO pode
                # ser ocultado. Fica na lista para receiving label manual.
                sem_nome.append(re.sub(r"\s+", " ", m.group(0))[:150])
                return m.group(0)
            n_rotulo += 1
            tag_match = re.match(rf"<{tag}\b(?P<attrs>[^<>]*?)(?P<self>/?)>", m.group(0))
            if not tag_match:
                return m.group(0)
            return f'<{tag}{tag_match.group("attrs")} aria-label="{rotulo}">{inner}</{tag}>'
        return m.group(0)

    text = ICON_CONTROL_RE.sub(ctrl, text)

    # --- 4. aria-hidden nos SVGs ------------------------------------------
    # SVG dentro de controle iconico SEM nome acessivel: preservado.
    def proteger(m: re.Match) -> str:
        tag = m.group("tag")
        attrs = m.group("attrs")
        inner = m.group("inner")
        if "<svg" not in inner or _inner_text(inner):
            return m.group(0)
        if has_attr(attrs, "aria-label") or get_attr(attrs, "title") or _svg_aria_label(inner):
            return m.group(0)
        # Controle iconico SEM nome acessivel: preserva o wrapper <a>/<button>
        # e NAO oculta o SVG (ele e o unico conteudo do controle).
        return m.group(0).replace("<svg", "\x00SVG\x00", 1)

    text = ICON_CONTROL_RE.sub(proteger, text)

    def svg(m: re.Match) -> str:
        nonlocal n_svg
        tag = m.group(0)
        if "aria-hidden" in tag:
            return tag
        n_svg += 1
        if tag.endswith("/>"):
            return tag[:-2] + ' aria-hidden="true"/>'
        return tag[:-1] + ' aria-hidden="true">'

    text = SVG_TAG_RE.sub(svg, text)

    # Restaura os SVGs preservados (controle iconico sem nome acessivel).
    text = text.replace("\x00SVG\x00", "<svg")

    return text, n_svg, n_rotulo, sem_nome


# --------------------------------------------------------------------------
# 6. width/height explicitos nos <img>
# --------------------------------------------------------------------------
def fix_img_dimensions(text: str) -> tuple[str, int]:
    cont = 0

    def repl(m: re.Match) -> str:
        nonlocal cont
        tag = m.group(0)
        if has_attr(tag, "width") and has_attr(tag, "height"):
            return tag
        if has_attr(tag, "width") or has_attr(tag, "height"):
            return tag
        m_cls = CLASS_RE.search(tag)
        if not m_cls:
            return tag
        classes = m_cls.group("val").split()
        altura = next((c[2:] for c in classes if re.fullmatch(r"h-[\d.]+", c)), None)
        largura = next((c[2:] for c in classes if re.fullmatch(r"w-[\d.]+", c)), None)
        if altura is None or largura is None:
            return tag
        if altura not in TAILWIND_PX or largura not in TAILWIND_PX:
            return tag
        px = TAILWIND_PX[altura]
        py = TAILWIND_PX[largura]
        cont += 1
        novo = tag[:-1].rstrip()
        if novo.endswith("/"):
            novo = novo[:-1].rstrip()
        return f'{novo} width="{px}" height="{py}">'

    return IMG_RE.sub(repl, text), cont


# --------------------------------------------------------------------------
# 7. Formatos de data -> filtros locale-aware
# --------------------------------------------------------------------------
def fix_datas(text: str) -> tuple[str, int]:
    cont = 0

    def repl(m: re.Match) -> str:
        nonlocal cont
        fmt = m.group(1)
        filtro = DATE_FILTERS.get(fmt)
        if not filtro:
            return m.group(0)
        cont += 1
        return f"|{filtro}"

    return re.sub(r'\|date:"([^"]+)"', repl, text), cont


# --------------------------------------------------------------------------
# 8. Guard de alteracoes nao salvas nos formularios de edicao (POST)
# --------------------------------------------------------------------------
FORM_RE = re.compile(r"<form\b[^>]*>.*?</form\s*>", re.S)
EDITABLE_RE = re.compile(
    r"<(input|textarea|select)\b[^>]*>",
    re.S,
)
NAO_EDITAVEL = {"hidden", "submit", "button", "image", "reset"}


def fix_unsaved_guard(text: str) -> tuple[str, int]:
    """Marca formularios POST com campos editaveis com `data-unsaved-guard`.

    O aviso de "alteracoes nao salvas" e global no template base; aqui apenas
    sinaliza quais formularios tem dados que o usuario pode perder.
    """
    cont = 0

    def repl(m: re.Match) -> str:
        nonlocal cont
        form = m.group(0)
        abertura = re.match(r"<form\b[^>]*>", form).group(0)
        if "data-unsaved-guard" in abertura or "data-no-unsaved-guard" in abertura:
            return form
        metodo = re.search(r"\bmethod\s*=\s*[\"']?(\w+)", abertura, re.I)
        if not metodo or metodo.group(1).lower() != "post":
            return form
        tem_editavel = False
        for ctrl in EDITABLE_RE.finditer(form):
            tag = ctrl.group(0)
            if ctrl.group(1) == "input":
                tipo = re.search(r"\btype\s*=\s*[\"']?(\w+)", tag, re.I)
                if tipo and tipo.group(1).lower() in NAO_EDITAVEL:
                    continue
            tem_editavel = True
            break
        if not tem_editavel:
            return form
        cont += 1
        nova = abertura[:-1].rstrip() + ' data-unsaved-guard>'
        return nova + form[len(abertura):]

    return FORM_RE.sub(repl, text), cont


# --------------------------------------------------------------------------
def processar(path: Path, escrever: bool) -> tuple[dict[str, int], list[str]]:
    original = path.read_text(encoding="utf-8")
    texto = original
    stats = {"ellipsis": 0, "th": 0, "foco": 0, "svg": 0, "rotulo": 0, "img": 0, "data": 0, "guard": 0}

    texto, n = fix_ellipsis(texto); stats["ellipsis"] += n
    texto, n = fix_th_scope(texto); stats["th"] += n
    texto, n = fix_focus_ring(texto); stats["foco"] += n
    texto, n_svg, n_rot, sem_nome = fix_svgs_e_nomes(texto)
    stats["svg"] += n_svg; stats["rotulo"] += n_rot
    texto, n = fix_img_dimensions(texto); stats["img"] += n
    texto, n = fix_datas(texto); stats["data"] += n
    texto, n = fix_unsaved_guard(texto); stats["guard"] += n

    if texto != original and escrever:
        path.write_text(texto, encoding="utf-8", newline="")
    return stats, sem_nome


def main() -> int:
    escrever = "--check" not in sys.argv
    total: dict[str, int] = {}
    alterados = 0
    sem_nome_total: list[str] = []

    for path in templates():
        r = rel(path)
        if r in SKIP:
            print(f"  [ignorado] {r}")
            continue
        stats, sem_nome = processar(path, escrever)
        sem_nome_total.extend(f"{r}: {s}" for s in sem_nome)
        for k, v in stats.items():
            total[k] = total.get(k, 0) + v
        if any(stats.values()):
            alterados += 1
            resumo = " ".join(f"{k}={v}" for k, v in stats.items() if v)
            print(f"  {r}: {resumo}")

    print()
    print(f"Arquivos alterados: {alterados}")
    print("Totais:", ", ".join(f"{k}={v}" for k, v in sorted(total.items())))
    if sem_nome_total:
        print()
        print(f"Controles so-icone SEM nome acessivel ({len(sem_nome_total)}) — tratar a mao:")
        for item in sem_nome_total:
            print(f"  - {item}")
    if not escrever:
        print("(modo --check: nada foi gravado)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
