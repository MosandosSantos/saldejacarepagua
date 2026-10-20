# Tasks: 005 — Problema Permissões

- [x] **T1. Decompor `_montar_contexto` (F→≤C)**
  - Acceptance: RF-01 — funções por seção, rank ≤ C; página /config/ comporta igual.
  - Verify: `radon cc acesso/views/config.py -s -n D` vazio; smoke de /config/ 200 para os 4 papéis.
  - Files: `acesso/views/config.py`.
  - ✅ Executado (03/10/2026): F(45) → 7 helpers `_ctx_*` + delegador `_eh_admin_com_tenant`; `radon cc acesso/views/config.py -n D` vazio; /config/ 200 (viewer, leitura própria).

- [x] **T2. Refatorar `_processar_etapa` (D) e view `equipe` (D)**
  - Acceptance: rank ≤ C; comportamento preservado.
  - Verify: radon sem rank D nesses arquivos; E2E de equipe (criar/editar/convidar) OK.
  - Files: `acesso/views/config.py`, `acesso/views/equipe.py`.
  - ✅ Executado (03/10/2026): `_processar_etapa` D(25) → `_ler_dados_etapa`/`_etapa_criar`/`_etapa_editar`/`_etapa_excluir`; view `equipe` D(28) → `_processar_reenvio_ativacao` + `_carregar_usuarios_equipe`; `radon cc acesso/views/config.py acesso/views/equipe.py -n D` vazio; regressão `guard_equipe` (admin_saas sem tenant → 302) corrigida e testada.

- [x] **T3. Suíte RBAC web (matriz papel × rota)**
  - Acceptance: RF-02 — `teste/test_rbac_web.py` cobre POSTs bloqueados para viewer e liberados para os demais, nas rotas de membros/potências/lojas/financeiro/equipe/config.
  - Verify: `pytest teste/test_rbac_web.py -v` verde.
  - Files: `teste/test_rbac_web.py` (novo), `teste/conftest.py`.
  - ✅ Executado (03/10/2026): 8 tests (`pytest teste/test_rbac_web.py -v` verde — viewer bloqueado em potências/lojas/equipe, viewer lê /config/ e edita só o próprio perfil, operacional sem equipe, admin_company com equipe).

- [x] **T4. Consolidar escopo de tenant/papel**
  - Acceptance: RF-03 — `qs_escopo` único em `acesso/` (ou `core/`), views o importam; cópias removidas.
  - Verify: grep mostra uma única definição; listagens respeitam tenant (teste existente de isolamento continua verde).
  - Files: `acesso/views/helpers.py` (ou novo módulo), views que definem cópia local.
  - ✅ Executado (03/10/2026): `grep -rn "def qs_escopo"` mostra única definição em `acesso/views/helpers.py:154`; views importam dela.

- [x] **T5. Varredura de rotas de escrita sem decorator**
  - Acceptance: RF-04 — script one-liner lista toda rota POST sem `web_login_required`/`web_requer_edicao`; resultado vazio.
  - Verify: script documentado em `scripts/` rodado com saída vazia.
  - Files: `scripts/audit_decorators.py` (novo).
  - ✅ Executado (03/10/2026): `python scripts/audit_decorators.py` → "OK — todas as rotas (exceto allowlist) têm decorator de autenticação"; dados_board sem rota direta; discador já tinha `@web_requer_admin`.
