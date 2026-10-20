# Tasks: 002 — Problema Pagamento

- [x] **T1. Context manager de transação em `core/gprb/connection.py`** — ✅ 2026-10-02
  - Implementado `gprb_transaction()` (psycopg3 `conn.transaction()` sobre a conexão thread-local; no-op em modo degradado).
  - Verify: `pytest teste/test_gprb_transaction.py` → **3 passed** (commit persiste, rollback descarta, integração com padrão do repositório).
  - Files: `core/gprb/connection.py`, `teste/test_gprb_transaction.py` (novo).

- [x] **T2. Aplicar transação em `definir_lojas_membro`** — ✅ 2026-10-02
  - Verify: `test_definir_lojas_rollback_em_falha_no_meio` — falha proposital no UPDATE final → **vínculos member_loja intactos** (rollback comprovado).
  - Files: `repositories/gprb_repository.py`, `teste/test_gprb_writes.py`.

- [x] **T3. Aplicar transação nas demais escritas** — ✅ 2026-10-02
  - Todas as 10 escritas do repositório (membros ×3, definir_lojas, lojas ×3, prefeituras ×3) usam `with gprb_transaction(), gprb_cursor() as cur:`; **zero `cur.connection.commit()` restantes** (grep vazio).
  - Verify: E2E real — POST nova potência → 302, linha gravada e depois removida; dashboard 200; log limpo.
  - Files: `repositories/gprb_repository.py`.

- [x] **T4. Corrigir/justificar os 7 B608** — ✅ 2026-10-02
  - 5 pontos: `# nosec B608` justificado na linha exata (fragments literais + valores parametrizados). 2 blocos multilinha `f'''`: convertidos para literal + `.replace('{where}', where)` com nosec no execute (comentário não pode entrar dentro de string tripla).
  - Verify: `bandit -r repositories/ core/gprb/ dashboard/repositories/` → **0 MEDIUM**.
  - Files: `core/gprb/members.py`, `core/gprb/ranking.py`, `dashboard/repositories/gprb_repository.py`, `repositories/gprb_repository.py`.

- [x] **T5. Testes de regressão das escritas GPRB (banco de teste)** — ✅ 2026-10-02
  - Banco dedicado `saldabritanea_test` criado com o schema de referência (13 tabelas); fixture `banco_gprb_teste` no conftest troca `GPRB_DB_NAME` e reseta a conexão thread-local.
  - Verify: `pytest teste/test_gprb_transaction.py teste/test_gprb_writes.py` → **8 passed** (0,84s).
  - Files: `teste/test_gprb_writes.py` (novo), `teste/conftest.py`, banco `saldabritanea_test`.
