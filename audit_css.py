# -*- coding: utf-8 -*-
"""Auditoria: classes usadas em templates/JS vs CSS compilado."""
import re
import os
from collections import defaultdict

# Caminhos relativos ao script: roda de qualquer lugar do projeto.
ROOT = os.path.dirname(os.path.abspath(__file__))
CSS = os.path.join(ROOT, "theme", "static", "css", "dist", "styles.css")
EXCLUDE_DIRS = {"node_modules", ".venv", "venv", ".git", "__pycache__", "static", "dist",
                ".agents", ".github", ".opencode", ".codex", ".impeccable", "DOCS", "skills"}
BAD_CHARS = set("()=?<>!&|;,")
STOPWORDS = {"if", "else", "for", "end", "const", "let", "var", "return",
             "true", "false", "null", "undefined", "function", "class", "this"}

def is_junk(tok):
    if any(c in BAD_CHARS for c in tok):
        return True
    if tok.startswith("_") or tok.startswith("$") or tok.startswith("{"):
        return True
    if "." in tok:  # classes Tailwind nao usam ponto cru no HTML
        return True
    if tok in STOPWORDS:
        return True
    return False


def unescape(s):
    s = s.replace("\\/", "/").replace("\\:", ":").replace("\\[", "[").replace("\\]", "]")
    s = s.replace("\\.", ".").replace("\\#", "#").replace("\\,", ",").replace("\\ ", " ")
    s = s.replace("\\%", "%")
    # escapes hex do CSS.escape: \32xl -> 2xl, \31 0 -> 10 (dígito inicial)
    s = re.sub(r"\\([0-9a-fA-F]{1,6})\s?", lambda m: chr(int(m.group(1), 16)), s)
    return s


used = defaultdict(set)      # classe -> set de arquivos
style_defs = set()           # classes definidas em <style> inline

for root, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.endswith("__pycache__")]
    for f in files:
        if not f.endswith((".html", ".js")):
            continue
        p = os.path.join(root, f)
        rel = os.path.relpath(p, ROOT)
        if any(x in rel.split(os.sep) for x in ("node_modules", ".venv", ".git")):
            continue
        src = open(p, encoding="utf-8", errors="ignore").read()

        # classes em atributos class="..."
        for m in re.finditer(r'''class\s*=\s*["']([^"']*)["']''', src):
            val = re.sub(r"\{[{%#][^}]*\}", " ", m.group(1))
            for tok in val.split():
                tok = tok.strip()
                if not tok or tok in ("{", "}", "{%", "%}"):
                    continue
                if tok.startswith("-") or tok.endswith("-") or "{" in tok or "}" in tok:
                    continue
                if is_junk(tok):
                    continue
                used[tok].add(rel)

        # classes definidas em <style> inline
        for sm in re.finditer(r"<style[^>]*>(.*?)</style>", src, re.S):
            for sel in re.findall(r"\.([A-Za-z_][A-Za-z0-9_-]*)\b", sm.group(1)):
                style_defs.add(sel)

css = open(CSS, encoding="utf-8", errors="ignore").read()
compiled = set()
for m in re.finditer(r"\.((?:\\.|[\w-])+)", css):
    compiled.add(unescape(m.group(1)))

missing = sorted(t for t in used if t not in compiled and t not in style_defs)

print("classes usadas nos templates/JS :", len(used))
print("selectors no CSS compilado       :", len(compiled))
print("classes em <style> inline        :", len(style_defs))
print("AUSENTES                         :", len(missing))
print("=" * 60)
for t in missing:
    loc = ", ".join(sorted(used[t])[:4])
    extra = "..." if len(used[t]) > 4 else ""
    print(f"  {t:45s} -> {loc}{extra}")

print("=" * 60)
print("Checagens especiais:")
for c in ["md:block", "md:flex", "lg:flex", "hidden", "grid-cols-2", "sm:grid-cols-2"]:
    print(f"  {c:20s} no CSS compilado: {c in compiled} | usada: {c in used}")
