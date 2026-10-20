# Corpo da Loja Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` for native execution, or `superpowers:subagent-driven-development` if the user selects subagent-driven execution. Follow the steps in order; each has its own test cycle.

**Goal:** Persist a required category for every Loja, backfill existing Lojas to Perfeição, and expose the category across Loja CRUD and Acompanhamento terminology.

**Architecture:** Add a fixed-choice `Loja.corpo` field with a Perfeição model default for legacy internal creators, while the web create/edit forms require an explicit valid choice. A migration assigns Perfeição to existing rows. Loja list/detail/forms show the value; the Acompanhamento filter remains based on member degree history, with the 15º–18º label changed to Capítulo.

**Tech Stack:** Django 5.2, Python 3.13, PostgreSQL, Django templates, Tailwind, pytest-django.

**Spec:** `specs/007-corpo-loja/spec.md`

## Global Constraints

- Keep the five fixed bodies and their degree ranges exactly as specified.
- Assign `perfeicao` to all Loja rows that exist when the migration runs; do not modify other Loja fields.
- Require a valid body in web create/edit POSTs, even though the model has a Perfeição compatibility default.
- Preserve existing tenant scoping and role permissions for Loja operations.
- `admin_saas` without a selected tenant may create a Loja only by explicitly choosing an active Vale; use that Vale's tenant and reject absent/inactive/unknown IDs.
- Keep Acompanhamento body filtering based on member degree history, not `Loja.corpo`.
- Do not add runtime dependencies or a separately managed body catalog.
- Run local tests against the CRM test database at `127.0.0.1:5434` through `core.settings_vale_test`, never the unrelated PostgreSQL service on port 5432.
- Leave the two user-confirmed baseline failures in `teste/test_loja_local.py` unchanged: missing posted `vale_id` in `test_create_loja_uses_selected_tenant_without_posted_vale`, and the `admin_saas` global-read expectation in `test_admin_saas_without_selected_tenant_cannot_use_loja_routes`.
- Exclude the existing oversized-parameter-ID case `test_upload_rejects_invalid_or_oversized_pdf` from Windows pytest runs because its node id exceeds the 32,767-character environment-variable limit for `PYTEST_CURRENT_TEST`.

## Review Focus

- Missing or forged `corpo` in create/edit POST must not write a Loja — pin in Task 2.
- Existing rows must be backfilled to Perfeição without changing other columns — pin in Task 1.
- A user from another tenant must not read or update a Loja while handling its body — retain and rerun tenant tests in Task 5.
- An invalid edit must not replace the saved body or lose the correct selected value on rerender — pin in Task 2.
- Capítulo must still match member degrees 15–18 and must not start filtering by Loja body — pin in Task 4.

---

## File Structure

- `contatos/models.py` owns the fixed `CORPO_CHOICES` and `Loja.corpo` field.
- `contatos/migrations/` records the schema change and Perfeição backfill.
- `contatos/views/gprb_lojas.py` parses/validates the POST value and prepares display/form values in the existing local CRUD flow.
- Loja templates render the selector and saved category; no other Loja behavior or permissions change.
- `contatos/views/acompanhamento.py` and its template keep the same degree filter but present Capítulo for 15º–18º.
- Focused tests live in `teste/test_loja_local.py`, `teste/test_loja_membro_models.py`, a migration test in `teste/test_loja_corpo_migration.py`, and `teste/test_acompanhamento_graus.py`.

### Task 1: Add the body choice field and backfill existing rows

**Files:**
- Modify: `contatos/models.py`
- Create: generated migration under `contatos/migrations/`
- Test: `teste/test_loja_membro_models.py`
- Test: `teste/test_loja_corpo_migration.py`

**Interfaces:**
- Produces `Loja.CORPO_CHOICES` with values `perfeicao`, `capitulo`, `kadosh`, `consistorio`, and `sc33`.
- Produces `Loja.corpo`, a non-null `CharField(max_length=20, choices=CORPO_CHOICES, default='perfeicao')`.

- [x] **Step 1: Write failing model tests**
  - `test_loja_corpo_choices_and_default_to_perfeicao` asserts the five specified values/labels and that an internal `Loja.objects.create(...)` without `corpo` receives `perfeicao`.
  - `test_existing_lojas_receive_perfeicao_when_migrated` creates a historical Loja at migration 0025, applies the new migration, and asserts its body is `perfeicao` while its name and number remain unchanged.
- [x] **Step 2: Run tests to verify RED**
  - Run: `.venv\Scripts\python.exe -m pytest --ds=core.settings_vale_test teste/test_loja_membro_models.py::test_loja_corpo_choices_and_default_to_perfeicao teste/test_loja_corpo_migration.py::test_existing_lojas_receive_perfeicao_when_migrated -q` with `VALE_TEST_DATABASE_URL` pointed at the test database on port 5434.
  - Expect failure because `Loja.corpo` and the new migration do not exist.
- [x] **Step 3: Implement the model field and migration**
  - Add `CORPO_CHOICES` and `Loja.corpo` with the approved values/default.
  - Generate the next migration after `0025_grau_grau_numero_4_33`; ensure adding the default populates all existing rows as `perfeicao`.
- [x] **Step 4: Run tests to verify GREEN**
  - Run the same command as Step 2; require both tests to pass and confirm the migrated historical row retains unrelated fields.

### Task 2: Validate and persist Corpo in create/edit

**Files:**
- Modify: `contatos/views/gprb_lojas.py`
- Modify: `contatos/templates/contatos/loja_nova.html`
- Modify: `contatos/templates/contatos/loja_editar.html`
- Test: `teste/test_loja_local.py`
- Update existing valid payloads: `teste/test_permissoes_vale_loja.py`

**Interfaces:**
- `_dados_da_loja(request)` includes the stripped `corpo` POST value.
- Create/edit contexts expose `Loja.CORPO_CHOICES` and the current/posted raw value for the selector.

- [x] **Step 1: Write failing create/edit tests**
  - Add `corpo='perfeicao'` to the valid test payload and assert create persists it; assert edit can change it to `capitulo`.
  - Add tests that missing and unknown body values return the form with an error and do not create/update the Loja.
  - Assert the create form has a required blank prompt and the edit form selects the saved body.
- [x] **Step 2: Run the named tests to verify RED**
  - Run: `.venv\Scripts\python.exe -m pytest --ds=core.settings_vale_test teste/test_loja_local.py -k "corpo" -q` with `VALE_TEST_DATABASE_URL` pointed at port 5434; expect missing persistence, validation, and selector behavior.
- [x] **Step 3: Implement server validation and selectors**
  - Parse `corpo`, validate it against `dict(Loja.CORPO_CHOICES)` before save, and preserve the submitted choice on error.
  - Add required selects to create/edit templates; on edit, initialize from the stored body.
- [x] **Step 4: Run create/edit tests to verify GREEN**
  - Run the same command as Step 2; confirm valid POSTs save, missing/unknown values leave database state unchanged, and both templates render all five choices.

### Task 3: Show Corpo in Loja list and detail

**Files:**
- Modify: `contatos/views/gprb_lojas.py`
- Modify: `contatos/templates/contatos/lojas.html`
- Modify: `contatos/templates/contatos/loja_detalhe.html`
- Test: `teste/test_loja_local.py`

**Interfaces:**
- `_para_contexto_loja(loja)` exposes `corpo` as the human-readable display label and a separate raw value only where an edit selector needs it.

- [x] **Step 1: Write failing display tests**
  - Add `test_loja_list_and_detail_display_corpo` and assert a Loja categorized as Capítulo shows “Capítulo” in both list and detail responses.
- [x] **Step 2: Run the test to verify RED**
  - Run: `.venv\Scripts\python.exe -m pytest --ds=core.settings_vale_test teste/test_loja_local.py::test_loja_list_and_detail_display_corpo -q` with `VALE_TEST_DATABASE_URL` pointed at port 5434; expect both rendered responses to omit the body label.
- [x] **Step 3: Implement display context and markup**
  - Add the body label to `_para_contexto_loja`, add a Corpo column to the list, update its empty/drill-down column spans, and show the body in the detail header/summary using existing HAZON badge styles.
- [x] **Step 4: Run the display test to verify GREEN**
  - Run the same command as Step 2; confirm list and detail show the saved label without changing tenant filtering.

### Task 4: Rename the 15º–18º Acompanhamento label

**Files:**
- Modify: `contatos/views/acompanhamento.py`
- Test: `teste/test_acompanhamento_graus.py`
- Update: `specs/006-acompanhamento-graus/spec.md` and its task notes

**Interfaces:**
- Keep the existing `grupo_grau=rosa_cruz` query identifier for compatibility; display its label as `Capítulo`, range `15º-18º`.

- [x] **Step 1: Write failing nomenclature test**
  - Update the preset rendering expectation to show Capítulo and not Rosa Cruz; retain tests asserting the preset returns members with degrees 15/18 and excludes 14/19.
- [x] **Step 2: Run the tests to verify RED**
  - Run: `.venv\Scripts\python.exe -m pytest --ds=core.settings_vale_test teste/test_acompanhamento_graus.py -k "preset or grupo" -q` with `VALE_TEST_DATABASE_URL` pointed at port 5434; expect the old visible label to fail while range behavior remains unchanged.
- [x] **Step 3: Change only the visible label/spec**
  - Rename the label to Capítulo without changing its member-degree query range or query identifier.
- [x] **Step 4: Run nomenclature and range tests to verify GREEN**
  - Run the same command as Step 2; confirm Capítulo displays and degree filtering remains 15º–18º.

### Task 5: Run integrated regression and runtime checks

**Files:** no additional product files unless a failing test identifies a scoped defect.

- [x] Run the full `teste/test_loja_local.py` module: `13 passed, 2 failed`; failures were exactly the two baseline nodes named above.
- [x] Run `.venv\Scripts\python.exe -m pytest --ds=core.settings_vale_test -k "not test_create_loja_uses_selected_tenant_without_posted_vale and not test_admin_saas_without_selected_tenant_cannot_use_loja_routes and not test_upload_rejects_invalid_or_oversized_pdf" teste/test_loja_local.py teste/test_loja_membro_models.py teste/test_loja_corpo_migration.py teste/test_loja_pdf_local.py teste/test_permissoes_vale_loja.py teste/test_acompanhamento_graus.py -q`: `71 passed, 5 deselected`.
- [x] Run `manage.py check` and `makemigrations --check --dry-run`: no issues/no changes.
- [x] Run Ruff on changed Python files; selective checks passed, excluding only recorded pre-existing findings in already-dirty files.
- [x] Run the layout detector on changed templates: no findings.
- [x] Rebuild the local app; container healthy, `/healthz/` HTTP 200, migration `0026_loja_corpo` applied, and both current Loja rows read `perfeicao`.
- [x] Report the existing full-suite CI blocker separately; do not expand this feature into unrelated suite repair.

### Task 6: Let `admin_saas` without tenant select a Vale for Loja creation

**Files:**
- Modify: `contatos/views/gprb_lojas.py`
- Test: `teste/test_saas_tenant_write_scope.py`

**Interfaces:**
- `loja_nova` may render for `ROLE_ADMIN_SAAS` without a session tenant and supplies only active Vales as choices.
- A submitted `vale_id` is resolved from that active-Vale queryset; `tenant_id` always comes from the resolved Vale, never directly from POST.
- Other roles and other routes retain their existing `web_requer_tenant_context` behavior.

- [x] **Step 1: Write failing SaaS tests**
  - Replace the old blanket unselected-admin denial test with coverage for: GET renders the Vale selector with no session tenant; POST with a valid active Vale and valid body creates under that Vale's tenant; missing, unknown, or inactive Vale returns an error and creates nothing.
- [x] **Step 2: Run tests to verify RED**
  - Run the named unselected-admin tests in `teste/test_saas_tenant_write_scope.py`; expect the tenant-context decorator/view guard to return 403 before rendering or resolving the Vale.
- [x] **Step 3: Implement the narrow exception**
  - Remove `web_requer_tenant_context` only from `loja_nova`; allow the SaaS role's `vale_sessao` to be `None`, retain the active Vale allowlist, and keep all other authorization and server validation.
- [x] **Step 4: Run SaaS tests to verify GREEN**
  - Confirm GET works, valid Vale POST persists the Loja under the selected Vale's tenant, and missing/invalid/inactive Vale never writes.
  - The four focused cases passed; the full module still has two separate documented baseline failures unrelated to this create flow.

### Task 7: Show only the degree columns for selected bodies

**Files:**
- Modify: `contatos/views/acompanhamento.py`
- Modify: `contatos/templates/contatos/acompanhamento.html`
- Test: `teste/test_acompanhamento_graus.py`
- Update: `specs/006-acompanhamento-graus/spec.md` and task notes

- [x] **Step 1: Write failing column-visibility tests**
  - For each body, assert only its inclusive degree range appears in `data-grau` headers and date cells; assert Membro/Presença remain and empty-state colspan matches visible columns.
  - Assert multiple selected bodies show the union of their degree columns and no selected body still shows 4º–33º.
- [x] **Step 2: Run tests to verify RED**
  - Run the new column-visibility tests; expect all 30 degree columns and fixed colspan regardless of body selection.
- [x] **Step 3: Filter rendered columns by selected body ranges**
  - Use the union of selected `GRAU_PRESETS[*]['numeros']` for both header and row date cells. Keep the existing member-row OR filter and keep Membro/Presença columns. No selection means all catalog degrees.
  - Replace fixed table minimum width with content-based sizing and compute the empty-state colspan as `2 + len(graus_visiveis)`.
- [x] **Step 4: Run tests to verify GREEN**
  - Confirm each body, multi-body union, default all columns, and fixed columns; `-k colunas` → `8 passed, 31 deselected`.

### Task 8: Final regression and runtime verification

- [x] Run the filtered integration suite from Task 5 plus `teste/test_saas_tenant_write_scope.py`; exclude the five documented test names (7 pytest cases): two `test_loja_local.py` failures, two unrelated `test_saas_tenant_write_scope.py` failures, and the Windows oversized-node-id PDF parametrization. Result: `90 passed, 7 deselected`.
- [x] Run Django/migration checks, targeted Ruff checks, and the layout detector: checks passed, detector `[]`.
- [x] Rebuild the app: container healthy, migration 0026 applied, local Loja rows remain `perfeicao`; `/healthz/` returned HTTP 200.
