# Tenant Code SCG33REAA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Use `superpowers:subagent-driven-development` only if the user explicitly chooses that approach.

**Goal:** Make `SCG33REAA` the configured external tenant code and rename the existing `GPRB` tenant row without changing its ID.

**Architecture:** Add one Django setting, `GPRB_TENANT_CODE`, and a resolver that honors explicit per-call codes before falling back to the setting. Refactor every external read/write path to use it. Provide a dry-run-first operation for the external `tenant.code` update; the live update runs only during the final cutover after all application code is ready.

**Tech Stack:** Python, Django settings, psycopg/PostgreSQL, pytest.

**Spec:** `DOCS/superpowers/specs/2026-10-10-amorio-tenant-navigation-brand-design.md`

## Global Constraints

- `GPRB_TENANT_CODE` defaults to `SCG33REAA` and is exposed through Django settings and Docker Compose.
- Tests using GPRB fixtures set `GPRB_TENANT_CODE=GPRB` explicitly.
- Update only `tenant.code` for the single existing `GPRB` row; preserve its `id`, all other tenant rows, and the user row.
- Direct-ID lookups and mutations, related-record selections, notification recipients, and cache-backed external data must be scoped to the configured tenant.
- External-data cache keys include the tenant code so old unscoped entries cannot be served after the cutover.
- Abort before writing if `GPRB` is missing/duplicated or `SCG33REAA` already exists.
- Do not repeat the completed member/shop/vale cleanup.
- Use the validated backup `backups/gprb_pre_bulk_delete_20261010_212731.dump` as the pre-cleanup recovery point.

## Review Focus

- Empty environment value: resolve to `SCG33REAA`; pin in `teste/test_gprb_tenant_config.py`.
- Explicit function argument: retain that code instead of the setting; pin in the same test.
- Missing or duplicate old tenant: abort without mutation; pin in `teste/test_rename_tenant_code.py`.
- Existing target code: abort without mutation; pin in `teste/test_rename_tenant_code.py`.
- Non-target tenants and the tenant primary key: remain unchanged; pin in the rename integration test.
- Direct IDs and cache entries from a foreign tenant: remain invisible; pin in `teste/test_gprb_tenant_isolation.py` and `teste/test_external_tenant_cache.py`.

---

### Task 1: Central tenant-code setting and resolver

**Files:**
- Modify: `core/settings.py`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `core/gprb/connection.py`
- Test: `teste/test_gprb_tenant_config.py`

**Interfaces:**
- Produce `resolve_tenant_code(explicit: str | None = None) -> str` in `core/gprb/connection.py`.
- The resolver returns the explicit non-empty code, otherwise `settings.GPRB_TENANT_CODE`.

- [ ] **Step 1: Write failing tests** `test_resolve_tenant_code_uses_scg_default`, `test_resolve_tenant_code_uses_scg_when_env_is_empty`, and `test_resolve_tenant_code_preserves_explicit_override`.
- [ ] **Step 2: Run** `python -m pytest teste/test_gprb_tenant_config.py -q`; expect failures because the setting/resolver is absent.
- [ ] **Step 3: Implement** `GPRB_TENANT_CODE = os.getenv('GPRB_TENANT_CODE', '').strip() or 'SCG33REAA'`, pass the same env variable to the app service in Compose, document it in `.env.example`, and add `resolve_tenant_code`.
- [ ] **Step 4: Run** `python -m pytest teste/test_gprb_tenant_config.py -q`; expect all tests to pass.

### Task 2: Route all external tenant reads and writes through the resolver

**Files:**
- Modify: `core/gprb/connection.py`
- Modify: `core/gprb/dashboard.py`
- Modify: `core/gprb/members.py`
- Modify: `core/gprb/ranking.py`
- Modify: `core/gprb/users.py`
- Modify: `dashboard/repositories/gprb_repository.py`
- Modify: `repositories/gprb_repository.py`
- Modify: `gestao/comunicacao.py`
- Modify: `teste/conftest.py`
- Test: `teste/test_gprb_tenant_consumers.py`

**Interfaces:**
- Consume `resolve_tenant_code` from Task 1.
- Functions accepting an optional `tenant_code` keep explicit values and resolve the setting only when the argument is omitted.

- [ ] **Step 1: Write failing integration tests** using `banco_gprb_teste`: `test_prefeitura_listing_uses_configured_tenant`, `test_dashboard_kpis_uses_configured_tenant`, and `test_explicit_tenant_code_overrides_config`. Create isolated test tenant rows and assert query results are scoped to the configured/explicit code.
- [ ] **Step 2: Run** `python -m pytest teste/test_gprb_tenant_consumers.py -q`; expect queries to use the current hard-coded `GPRB`.
- [ ] **Step 3: Replace** production defaults and raw SQL literals with `resolve_tenant_code`; update the GPRB test fixture to explicitly set and restore `GPRB_TENANT_CODE=GPRB`.
- [ ] **Step 4: Run** `python -m pytest teste/test_gprb_tenant_consumers.py teste/test_gprb_writes.py -q`; expect all focused tests to pass.
- [ ] **Step 5: Search production Python sources** for operational `tenant_code='GPRB'` defaults and `code = 'GPRB'` filters; only explicit test fixtures and the guarded rename operation may retain the literal.

### Task 3: Add a guarded external tenant-code rename operation

**Files:**
- Create: `scripts/renomear_codigo_tenant.py`
- Test: `teste/test_rename_tenant_code.py`

**Interfaces:**
- Provide `renomear_codigo_tenant(conn, codigo_atual: str, codigo_novo: str) -> int`.
- CLI accepts `--old GPRB --new SCG33REAA`; default is dry-run, and mutation requires `--apply`.

- [ ] **Step 1: Write failing tests** against `banco_gprb_teste` for a successful rename preserving the same tenant `id`, absent/duplicate old code, and target-code collision.
- [ ] **Step 2: Run** `python -m pytest teste/test_rename_tenant_code.py -q`; expect the rename function not to exist.
- [ ] **Step 3: Implement** a transaction that locks/reads the tenant rows, enforces the preconditions, updates only `tenant.code`, verifies one affected row, and rolls back on any mismatch. The CLI must print the tenant ID and proposed change in dry-run mode without writing.
- [ ] **Step 4: Run** `python -m pytest teste/test_rename_tenant_code.py -q`; expect all tests to pass.
- [ ] **Step 5: Verify dry-run** against the connected database and require exactly one old-code row and no target-code row. Do not use `--apply` until the integrated cutover task in the brand plan.

### Task 4: Scope direct IDs, auxiliary reads, and tenant-derived caches

**Files:**
- Modify: `repositories/gprb_repository.py`
- Modify: `core/gprb/users.py`
- Modify: `core/gprb/members.py`
- Modify: `candidatos/views/api.py`
- Modify: `recepcao/views/helpers.py`
- Modify: `tarefas/views.py`
- Modify: `tarefas/management/commands/enviar_lembretes_eventos.py`
- Test: `teste/test_gprb_tenant_isolation.py`
- Test: `teste/test_external_tenant_cache.py`

**Interfaces:**
- `emails_membros_da_loja(loja_id, tenant_code=None) -> list[tuple[str, str]]` returns active, emailed members whose primary shop belongs to the configured tenant.
- Cache namespaces for GPRB-derived prefeitura/shop data include `GPRB_TENANT_CODE`.

- [ ] **Step 1: Write failing isolation tests** for foreign member/shop/prefeitura direct IDs, direct mutations, cross-tenant member/shop links, option/autocomplete lists, user-by-ID update/delete, and event-email recipient scoping.
- [ ] **Step 2: Run** `python -m pytest teste/test_gprb_tenant_isolation.py -q`; expect foreign IDs/data to be returned or mutated.
- [ ] **Step 3: Add cache isolation tests** that seed the legacy unscoped cache keys and assert the configured tenant's API/helper results are loaded instead.
- [ ] **Step 4: Run** `python -m pytest teste/test_external_tenant_cache.py -q`; expect stale unscoped entries to fail.
- [ ] **Step 5: Add** tenant ID/code predicates to detail, update, delete, count, select, and related-record queries; reject attempts to link a member/store/prefeitura from another tenant.
- [ ] **Step 6: Namespace** API and reception cache keys by tenant code; scope their SQL queries; route both scheduled-event email paths through `emails_membros_da_loja`.
- [ ] **Step 7: Run** `python -m pytest teste/test_gprb_tenant_isolation.py teste/test_external_tenant_cache.py teste/test_gprb_tenant_consumers.py teste/test_gprb_writes.py -q`; expect all isolation and write-scope tests to pass.
