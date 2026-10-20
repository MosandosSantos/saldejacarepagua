# Tasks: 001 — Problema Autenticação

- [x] **T1. Remover BOM de `tarefas/views.py`** — ✅ 2026-10-02
  - Acceptance: primeiro byte do arquivo ≠ EF BB BF; `radon cc tarefas/views.py` sem erro.
  - Verify: `head -c 3` → `22 22 22`; radon parseia (1 função C encontrada).
  - Files: `tarefas/views.py`.

- [x] **T2. B104 em `helpers.py`** — ✅ 2026-10-02 (corrigido como **falso positivo**)
  - Nota: o flag não era bind de servidor — era fallback de IP para chave de rate limit (`client_ip`). Correção: `# nosec B104` justificado inline; comportamento preservado.
  - Verify: `bandit -r acesso/ -q` → 0 MEDIUM.
  - Files: `acesso/views/helpers.py`.

- [x] **T3. Testes de login web (espelho + fallback + rate limit)** — ✅ 2026-10-02
  - Acceptance: RF-03 coberto; 6ª tentativa bloqueada mesmo com senha correta.
  - Verify: `pytest teste/test_login_web.py -v` → **7 passed** (login ok, sessão ativa, senha inválida, inexistente, rate limit, espelho criado, espelho reutilizado).
  - Files: `teste/test_login_web.py` (novo).

- [x] **T4. Testes do ciclo de convite/ativação** — ✅ já coberto (verificado)
  - Acceptance: RF-04 — uso único, expiração e limite de reenvio já testados no arquivo existente.
  - Verify: `pytest teste/test_ativacao_web.py -q` → **6 passed**.
  - Files: `teste/test_ativacao_web.py` (sem alteração).

- [x] **T5. Documentar decisão do rate limit volátil** — ✅ 2026-10-02
  - Acceptance: aceite registrado (v1: cache volátil OK para localhost single-tenant; persistir em banco se expor publicamente).
  - Verify: entrada nº 11 em `specs/legacy/known-problems.md` atualizada.
  - Files: `specs/legacy/known-problems.md`.
