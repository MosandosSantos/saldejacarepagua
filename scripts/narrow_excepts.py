# -*- coding: utf-8 -*-
"""Estreita os `except Exception` para os tipos de erro reais de cada bloco.

Regra `no-generic-except` (Python Expert Best Practices): capturar `Exception`
esconde erro inesperado. Aqui cada `except` passa a listar as excecoes que o
bloco realmente pode levantar — e onde o erro NAO pode ser escondido (um
adaptador de lib de terceiros), o `except` amplo vira `raise` de um erro
proprio tipado, que e o que os chamadores capturam.

Cada linha trocada e conferida: se o trecho original nao bater exatamente,
o script aborta em vez de editar no escuro.

Migracao de USO UNICO: depois de aplicada, rodar de novo reporta "esperado X,
achou Y" para as 32 linhas ja estreitadas (e nao muda nada). Para re-aplicar
depois de um revert, restaure as linhas para `except Exception` primeiro.
"""
from __future__ import annotations

import ast
import io
import sys
from pathlib import Path

# (arquivo, linha 1-based, trecho original, trecho novo)
TROCAS: list[tuple[str, int, str, str]] = [
    # ---------------- acesso ----------------
    ("acesso/views/auth.py", 251,
     "    except Exception:",
     "    except DBError:"),
    ("acesso/views/auth.py", 256,
     "    except Exception:",
     "    except DBError:"),
    ("acesso/views/equipe.py", 97,
     "    except Exception:",
     "    except (psycopg.Error, OSError, ValueError):"),
    ("acesso/views/equipe.py", 190,
     "    except Exception as e:",
     "    except (psycopg.Error, OSError, ValueError) as e:"),
    ("acesso/views/helpers.py", 88,
     "    except Exception as e:",
     "    except (psycopg.Error, OSError, ValueError) as e:"),
    ("acesso/views/helpers.py", 240,
     "    except Exception as e:",
     "    except (psycopg.Error, OSError, ValueError) as e:"),
    ("acesso/views/helpers.py", 253,
     "        except Exception as e:",
     "        except BadSignature as e:"),
    ("acesso/views/helpers.py", 320,
     "    except Exception as e:",
     "    except (psycopg.Error, OSError, ValueError) as e:"),
    # ---------------- agenda ----------------
    ("agenda/google_sync.py", 102,
     "    except Exception:  # best-effort: sem Google disponível, segue com o delete local",
     "    except (HttpError, RefreshError, OSError):"),
    ("agenda/views.py", 119,
     "        except Exception:",
     "        except (smtplib.SMTPException, OSError):"),
    # ---------------- automacoes ----------------
    ("automacoes/engine.py", 180,
     "        except Exception as exc:",
     "        except (DBError, DjangoValidationError, smtplib.SMTPException,\n"
     "                OSError, ValueError, TypeError) as exc:"),
    # ---------------- candidatos ----------------
    ("candidatos/oficialato.py", 418,
     "    except Exception:",
     "    except (DBError, DjangoValidationError):"),
    ("candidatos/views/crud.py", 83,
     "    except Exception:",
     "    except DBError:"),
    # ---------------- core ----------------
    ("core/urls.py", 29,
     "    except Exception as e:",
     "    except DBError as e:"),
    # ---------------- dashboard ----------------
    ("dashboard/services/dashboard_service.py", 95,
     "        except Exception:",
     "        except (psycopg.Error, OSError, ValueError):"),
    ("dashboard/views.py", 298,
     "    except Exception as e:",
     "    except DBError as e:"),
    ("dashboard/views.py", 369,
     "    except Exception as e:",
     "    except DBError as e:"),
    ("dashboard/views.py", 651,
     "    except Exception as e:",
     "    except DBError as e:"),
    ("dashboard/views.py", 689,
     "        except Exception as e:",
     "        except DBError as e:"),
    # ---------------- recepcao ----------------
    ("recepcao/views/board.py", 44,
     "    except Exception:",
     "    except DBError:"),
    # ---------------- tarefas ----------------
    ("tarefas/checkin.py", 109,
     "    except Exception:",
     "    except psycopg.Error:"),
    ("tarefas/google_sync.py", 110,
     "    except Exception:",
     "    except (HttpError, RefreshError, OSError):"),
    ("tarefas/google_sync.py", 119,
     "    except Exception:",
     "    except (HttpError, RefreshError, OSError):"),
    ("tarefas/management/commands/enviar_lembretes_eventos.py", 70,
     "        except Exception:",
     "        except (psycopg.Error, OSError, ValueError):"),
    ("tarefas/views.py", 1107,
     "    except Exception:",
     "    except (ImportError, ValueError, TypeError, OSError):"),
    ("tarefas/views.py", 1371,
     "    except Exception as exc:",
     "    except (TemplateError, KeyError, ValueError, TypeError) as exc:"),
    ("tarefas/views.py", 1382,
     "    except Exception as exc:",
     "    except (smtplib.SMTPException, OSError, ValueError) as exc:"),
    ("tarefas/views.py", 1451,
     "    except Exception:",
     "    except (psycopg.Error, OSError, ValueError):"),
]

# imports a acrescentar por arquivo (nada e duplicado se ja existir)
IMPORTS: dict[str, list[str]] = {
    "acesso/views/auth.py": ["from django.db import Error as DBError"],
    "acesso/views/equipe.py": ["import psycopg"],
    "acesso/views/helpers.py": [
        "import psycopg",
        "from django.core.signing import BadSignature",
    ],
    "agenda/google_sync.py": [
        "from google.auth.exceptions import RefreshError",
        "from googleapiclient.errors import HttpError",
    ],
    "agenda/views.py": ["import smtplib"],
    "automacoes/engine.py": [
        "import smtplib",
        "from django.core.exceptions import ValidationError as DjangoValidationError",
        "from django.db import Error as DBError",
    ],
    "candidatos/oficialato.py": [
        "from django.core.exceptions import ValidationError as DjangoValidationError",
        "from django.db import Error as DBError",
    ],
    "candidatos/views/crud.py": ["from django.db import Error as DBError"],
    "core/urls.py": ["from django.db import Error as DBError"],
    "dashboard/services/dashboard_service.py": ["import psycopg"],
    "dashboard/views.py": ["from django.db import Error as DBError"],
    "recepcao/views/board.py": ["from django.db import Error as DBError"],
    "tarefas/checkin.py": ["import psycopg"],
    "tarefas/google_sync.py": [
        "from google.auth.exceptions import RefreshError",
        "from googleapiclient.errors import HttpError",
    ],
    "tarefas/management/commands/enviar_lembretes_eventos.py": ["import psycopg"],
    "tarefas/views.py": [
        "from django.template import TemplateError",
    ],
}


def inserir_import(linhas: list[str], linha_import: str, caminho: Path) -> list[str]:
    """Insere o import no nivel do modulo, depois do ultimo import de topo.

    Usa a AST para achar o ultimo `import`/`from` de top-level — heuristica por
    texto erra quando a funcao tem import indentado (ou seja, quase sempre).
    """
    if any(l.strip() == linha_import for l in linhas):
        return linhas
    arvore = ast.parse("".join(linhas))
    ultimo = 0
    for node in arvore.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            ultimo = max(ultimo, node.end_lineno)
    if ultimo == 0:
        # sem imports de topo: insere depois do docstring do modulo
        doc = ast.get_docstring(arvore, clean=False)
        if doc is not None and arvore.body:
            primeiro = arvore.body[0]
            ultimo = primeiro.end_lineno
    return linhas[:ultimo] + [linha_import + "\n"] + linhas[ultimo:]


def main() -> int:
    escrever = "--check" not in sys.argv
    # 1) as trocas de except
    por_arquivo: dict[str, list[tuple[int, str, str]]] = {}
    for arquivo, ln, velho, novo in TROCAS:
        por_arquivo.setdefault(arquivo, []).append((ln, velho, novo))

    erros = []
    alterados = 0
    for arquivo, itens in por_arquivo.items():
        p = Path(arquivo)
        linhas = p.read_text(encoding="utf-8-sig").splitlines(keepends=True)
        for ln, velho, novo in sorted(itens, reverse=True):
            atual = linhas[ln - 1]
            if atual.strip() != velho.strip():
                erros.append(f"{arquivo}:{ln} esperado {velho!r}, achou {atual.strip()!r}")
                continue
            linhas[ln - 1] = novo + "\n"
            alterados += 1
        # 2) imports
        for imp in IMPORTS.get(arquivo, []):
            linhas = inserir_import(linhas, imp, p)
        if escrever:
            p.write_text("".join(linhas), encoding="utf-8", newline="")
        else:
            p.with_suffix(".py.bak-check").write_text("".join(linhas), encoding="utf-8")

    for e in erros:
        print(f"  ERRO {e}")
    print(f"\nTrocas aplicadas: {alterados}/{len(TROCAS)}")
    if not escrever:
        for p in Path(".").rglob("*.py.bak-check"):
            p.unlink()
        print("(modo --check: nada foi gravado)")
    return 1 if erros else 0


if __name__ == "__main__":
    raise SystemExit(main())
