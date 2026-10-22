#!/usr/bin/env python
"""Smoke test das rotas web autenticadas.

Roda dentro do container (o codigo e os dados vivem la) e devolve o status de
cada rota. Um 500 aqui significa que o ultimo refactor quebrou a view.

Uso:  docker exec gprbr-app python /tmp/smoke_routes.py
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, "/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django  # noqa: E402

django.setup()

from django.test import Client  # noqa: E402

from acesso.models import Usuario  # noqa: E402

ROTAS = [
    "/dashboard/", "/contatos/", "/membros/", "/lojas/", "/vales/",
    "/contatos/carteiras/", "/tarefas/", "/agendas/?modo=calendario",
    "/agendas/?modo=kanban", "/agendas/?modo=lista", "/emails/", "/automacoes/",
    "/iniciacao/", "/recepcao/", "/equipe/",
    "/config/", "/agenda/", "/agenda/novo/", "/login/",
]


def main() -> int:
    u = Usuario.objects.filter(status="ativo").order_by("id").first()
    if u is None:
        print("Nenhum usuario ativo para o smoke test")
        return 1
    c = Client()
    s = c.session
    s["usuario_id"] = str(u.id)
    s["usuario"] = {"id": str(u.id), "nome": u.nome, "email": u.email, "role": u.role}
    s.save()

    erros = []
    for r in ROTAS:
        try:
            resp = c.get(r)
            st = resp.status_code
            if st >= 500:
                erros.append((r, st, resp.content.decode("utf-8", "replace")[:2000]))
            print(f"  {r:34} -> {st}")
        except Exception as e:  # noqa: py-rules — o smoke test reporta, nao quebra
            erros.append((r, "EXC", repr(e)))
            print(f"  {r:34} -> EXC {e!r:.90}")

    print()
    print(f"ERROS 5xx: {len(erros)}")
    for r, st, body in erros:
        print(f"  {r} {st}")
        m = re.search(r'<pre class="exception_value">(.*?)</pre>', body, re.S)
        print("   ", (m.group(1) if m else body)[:400])
    return 1 if erros else 0


if __name__ == "__main__":
    raise SystemExit(main())
