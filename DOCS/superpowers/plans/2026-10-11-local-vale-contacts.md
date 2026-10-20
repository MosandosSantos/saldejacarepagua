# Local Vale Contacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Vale CRUD's disabled GPRB dependency with a tenant-scoped local Django table and add Secretary/Treasurer names and contact details.

**Architecture:** Add a local `Vale` model in `contatos`, stored in Docker `saldabritanea`, and route the existing Vale URLs through ORM-backed views. The table starts empty; no external GPRB data is imported. Keep current URLs and annual storage semantics while displaying the agreed `Delegado` and `Mensalidade` terminology.

**Tech Stack:** Django 5.2, PostgreSQL 15, Django migrations, pytest-django.

**Spec:** `DOCS/superpowers/specs/2026-10-11-local-vale-contacts-design.md`

## Global Constraints

- A persistência será local, no banco Docker `saldabritanea`.
- A nova tabela começa vazia. Os Vales existentes serão recadastrados manualmente; nenhum dado da instância externa será importado.
- Nesta etapa, Vale não terá vínculos locais com Loja ou Membro. Contagens de Lojas/Membros e bloqueios de exclusão baseados nesses vínculos ficam adiados.
- Secretaria e Tesouraria serão exibidas com **nome, e-mail e telefone** na consulta e na confirmação de exclusão.
- Os e-mails serão armazenados como texto, sem acrescentar um validador mais restritivo; o exemplo fornecido (`farelli@gprbr`) precisa continuar aceito.
- A UI usa **Mensalidade**, mas os campos e a semântica anual existentes (`valor_anuidade`, `vencimento_anuidade`) não mudam nesta etapa.
- Manter as rotas atuais de Vale (`/contatos/prefeituras/` e `/contatos/prefeitura/...`) e o campo interno `prefeito` para compatibilidade; não renomear rotas nem chaves internas.
- O acesso SQL GPRB permanece desativado. Não consultar, copiar ou alterar a instância PostgreSQL externa `saldabritanea`.
- A tabela `vales` deve ser criada no banco Docker ativo sem importar dados. Fazer backup `pg_dump -Fc` fora do repositório antes de aplicar DDL.
- Não remover volumes, não usar `docker compose down -v`, não alterar `gprbr` ou `esfera-postgres` e nunca tocar em `esferasda`.
- `pytest.ini` defaults to fail-closed `core.settings_vale_test`; database tests require explicit `VALE_TEST_DATABASE_URL`. Local tests run through a Compose one-off app container; CI uses its isolated PostgreSQL service URL.
- Os heads de migration atuais são `acesso.0019_retire_admin_company_operacional` e `contatos.0014_lojapdf` (versionados no commit `2f035b9`). A nova migration deve seguir esses heads.
- Migrations `candidatos.0004`, `recepcao.0003` e `tarefas.0007` estão aplicadas no container, mas seus arquivos e mudanças correspondentes são trabalho local fora do escopo Vale. Não as stagear neste trabalho; revisar/versionar separadamente antes de uma entrega limpa.
- A configuração `core.settings_vale_test` exige `VALE_TEST_DATABASE_URL` para o PostgreSQL Docker como role `gprbr`; não usar as configurações ambiente do host (`localhost`/role `postgres`). Execute os testes em container temporário Compose, com código montado em `/app`.
- Não resetar `test_saldabritanea` nem qualquer banco fora de `gprbr-db`. Os testes desta feature usam o banco dedicado `test_saldabritanea_vales` no Docker.
- Preservar as demais alterações não relacionadas do workspace; revisar/stagear somente os arquivos e hunks deste plano.

## Review Focus

- **`public.vales` já existe no banco Docker:** interromper e inspecionar; nunca apagar ou sobrescrever dados. Task 6 verifica `to_regclass('public.vales')` antes da migration.
- **Uma rota local tenta chamar o conector GPRB:** o CRUD deve funcionar com `GPRB_DB_ENABLED=False`; Task 2 falha se `connect()` for chamado.
- **Usuário altera tenant ou ID para alcançar Vale de outro tenant, ou um usuário sem tenant tenta usar a exceção global:** operações devem respeitar o tenant; somente `admin_saas` pode ler globalmente sem tenant, e escritas sem contexto válido são bloqueadas. Task 2 cobre esses casos.
- **E-mail legado como `farelli@gprbr` ou campos de contato vazios:** os valores devem ser preservados; Tasks 1–2 cobrem round-trip e opcionais.
- **Vale não tem vínculo local com Loja/Membro:** consulta e exclusão não podem consultar o GPRB, inventar contagens ou bloquear com relações externas; Tasks 2–3 cobrem o comportamento independente.

---

### Task 1: Local Vale model and migration

**Files:**
- Create: `core/settings_vale_test.py`
- Modify: `contatos/models.py`
- Create: `contatos/migrations/0015_vale.py`
- Create: `teste/test_vale_local.py`

**Interfaces:**
- Produces `contatos.models.Vale`, stored in `vales`, with a required FK to `acesso.Tenant`, `db_column='tenant_id'`, and `related_name='vales'`.
- Fields: `nome` (CharField 160); `sigla` (CharField 10, optional); `prefeito` (CharField 160, optional, internal compatibility key displayed as Delegado); `telefone` (CharField 40, optional); `email` (CharField 254, optional); `secretario_nome`/`tesoureiro_nome` (CharField 160, optional); `secretario_email`/`tesoureiro_email` (CharField 254, optional); `secretario_telefone`/`tesoureiro_telefone` (CharField 40, optional); `pix` (CharField 255, optional); `valor_anuidade` (DecimalField 12,2, nullable); `vencimento_anuidade` (nullable DateField); `status` (CharField 10, default `ATIVA`); `created_at` and `updated_at`.
- `Meta.db_table = 'vales'`, `ordering = ['nome']`; no unique-name constraint or external relation is added.
- `core.settings_vale_test` requires explicit `VALE_TEST_DATABASE_URL` validated for local Docker host/role/database, sets `TEST.NAME = 'test_saldabritanea_vales'`, and keeps `GPRB_DB_ENABLED = False`. Missing or non-Docker URLs fail closed.
- Migration dependencies: `contatos.0014_lojapdf` and `acesso.0019_retire_admin_company_operacional`.

- [x] **Step 1: Add the isolated test settings module**

Create `core/settings_vale_test.py` that refuses to load unless `VALE_TEST_DATABASE_URL` explicitly targets either Docker `saldabritanea` as role `gprbr` via `db`, `localhost`, or `127.0.0.1`, or the ephemeral CI database `gprbr_test` as role `postgres`. Parse the URL into the database settings, set `DATABASES['default']['TEST']['NAME']` to `test_saldabritanea_vales`, and keep `GPRB_DB_ENABLED=False`. Set `pytest.ini` to use these safe settings by default and update CI to supply its isolated service URL. Never fall back to host PostgreSQL defaults.

- [x] **Step 2: Write the failing Vale model tests**

Create `teste/test_vale_local.py` with `test_vale_test_settings_require_explicit_database_url`, `test_vale_test_settings_reject_external_database_url`, `test_pytest_defaults_to_fail_closed_database_settings`, `test_vale_views_import_without_uncommitted_tenant_decorator`, `test_vale_model_is_registered`, `test_vale_uses_local_table_and_tenant_fk`, `test_vale_contact_fields_round_trip`, and `test_vale_preserves_local_domain_email_and_blank_contacts`. Put model imports inside tests so the missing model fails cleanly before implementation. Assert the settings subprocess refuses absent/external URLs, local Vale views import with only committed access helpers, `farelli@gprbr` round-trips unchanged, and empty contact fields remain empty.

- [x] **Step 3: Run the model-presence test and verify RED**

Run the model-presence test without a database using `.venv/Scripts/python.exe -m pytest --ds=core.settings teste/test_vale_local.py::test_vale_model_is_registered -q`.

Expected: FAIL because `contatos.models.Vale` is not defined. This test does not need a database.

- [x] **Step 4: Implement `Vale` and generate `0015_vale`**

Add the model fields from the Interfaces block to `contatos/models.py`; use `CharField` for e-mail values, not `EmailField`. Run `.venv/Scripts/python.exe manage.py makemigrations contatos` and inspect the generated migration: it must create only the empty `vales` table and depend on the current `acesso` and `contatos` migration heads. Do not add a data migration or external query.

- [x] **Step 5: Verify schema and model behavior on the dedicated test DB**

Preflight that `test_saldabritanea_vales` is absent in `gprbr-db`. Run tests in a Compose one-off app container with the workspace bound at `/app`: `docker compose run --rm --no-deps -v "$($PWD.Path):/app" --entrypoint sh app -c 'VALE_TEST_DATABASE_URL="$DATABASE_URL" python -m pytest --ds=core.settings_vale_test --create-db teste/test_vale_local.py -q'`. Run migration drift check with `.venv/Scripts/python.exe manage.py makemigrations --check --dry-run contatos` (no DB access required). Never run Vale pytest commands under ambient host settings; the Docker runner supplies the verified Docker URL without printing credentials.

Expected: all model tests pass; only the dedicated test DB is created; no model changes remain ungenerated. Never reset `test_saldabritanea`.

- [x] **Step 6: Commit the model slice**

Commit only `core/settings_vale_test.py`, `contatos/models.py`, `contatos/migrations/0015_vale.py`, and `teste/test_vale_local.py`.

### Task 2: Tenant-scoped ORM CRUD

**Files:**
- Create: `contatos/views/vales.py`
- Modify: `contatos/views/__init__.py`
- Modify: `teste/test_potencia_web.py`

**Interfaces:**
- Exports `prefeituras(request)`, `prefeitura_nova(request)`, `prefeitura_editar(request, pk)`, and `prefeitura_excluir(request, pk)` from `contatos.views.vales`; `contatos.urls` keeps the existing route names and paths.
- Uses `filtro_tenant(request, Vale.objects.all())` for reads and object lookups; only `admin_saas` may use its documented global-read exception. Other tenantless users fail closed. Writes keep `web_login_required`, `web_requer_tenant_context`, and `web_requer_edicao`.
- Preserves template context keys `prefeituras`, `prefeitura`, `erro`, and existing form POST keys, including internal `prefeito`.
- `prefeitura_lojas_json` remains the separate legacy endpoint; local Vale CRUD and its list do not call it or `repositories.gprb_repository`.

- [x] **Step 1: Replace GPRB-dependent CRUD tests with local ORM tests**

Update `teste/test_potencia_web.py` to stop using `banco_gprb_teste`, raw GPRB SQL, and repository assertions. Cover `test_create_vale_persists_all_contact_fields`, `test_edit_vale_updates_contacts`, `test_list_vales_is_tenant_scoped`, `test_admin_saas_without_tenant_can_list_all_vales`, `test_unselected_admin_saas_cannot_create_vale`, `test_tenantless_non_saas_cannot_list_vales`, and `test_delete_vale_deletes_only_local_record`. Use unique tenant slugs and emails, and a `grande_prior` user with a session fixture for editor flows (`admin_company`/`operacional` were retired). Leave the broader untracked `teste/test_saas_tenant_write_scope.py` untouched.

- [x] **Step 2: Run the local CRUD tests and verify RED**

Run with the same temporary Compose container and explicit `VALE_TEST_DATABASE_URL`, using `--reuse-db` and `teste/test_potencia_web.py`.

Expected: create/edit/list/delete tests fail because the routed views still call the disabled GPRB repository.

- [x] **Step 3: Implement ORM-backed Vale views**

Implement the four view functions in `contatos/views/vales.py`. Parse BRL amounts with `normalizar_valor`, parse the existing ISO due-date input, and map query results into the template context keys from the Interfaces block. Scope all queries and `get_object_or_404` lookups with `filtro_tenant`; do not import `core.gprb.connection` or the GPRB repository.

- [x] **Step 4: Wire exports and preserve permission boundaries**

Re-export the local CRUD functions from `contatos/views/__init__.py`, retaining the legacy JSON endpoint separately. Verify tenantless non-SaaS users cannot read all Vales, and SaaS admins without a selected tenant receive the existing forbidden response for writes.

- [x] **Step 5: Verify CRUD, isolation, and connector independence**

Run with the same temporary Compose container and explicit `VALE_TEST_DATABASE_URL`, using `--reuse-db` and `teste/test_potencia_web.py`.

Expected: all local CRUD tests pass, cross-tenant IDs are inaccessible, only `admin_saas` gets the tenantless global-read exception, writes without a valid tenant are blocked, and a patched GPRB connector is never called.

- [x] **Step 6: Commit the ORM CRUD slice**

Commit only `contatos/views/vales.py`, the package export hunk, and the updated Vale/tenant-scope tests.

### Task 3: Vale navigation and contact entry forms

**Files:**
- Modify: `acesso/context_processors.py` (Vale nav item only)
- Modify: `contatos/templates/contatos/prefeitura_nova.html`
- Modify: `contatos/templates/contatos/prefeitura_editar.html`
- Create: `teste/test_vale_templates.py`
- Create: `teste/test_vale_navigation.py`
- Test: `teste/test_delegado_labels.py`, `teste/test_mensalidade_labels.py`

**Interfaces:**
- Create/edit post `secretario_nome`, `secretario_email`, `secretario_telefone`, `tesoureiro_nome`, `tesoureiro_email`, and `tesoureiro_telefone`.

- [x] **Step 1: Write failing navigation and form tests**

Create `teste/test_vale_templates.py` with `test_create_and_edit_show_both_contact_groups` before the form edits. The Vale navigation tuple was already present in the approved workspace UI; add `teste/test_vale_navigation.py` as a regression test for its existing order and URL. The form test asserts both names plus existing e-mail/phone inputs, optional behavior, and no seeded example values.

- [x] **Step 2: Run template tests and verify RED**

Run with the same temporary Compose container and explicit `VALE_TEST_DATABASE_URL`, using `--reuse-db` and the listed navigation/form/label tests.

Expected: the form test fails because the new name inputs are absent; the navigation regression passes because its UI change predates this CRUD work.

- [x] **Step 3: Update the create/edit forms**

Preserve the existing Vale nav tuple immediately after Dashboard and its current URL. Add the two optional name inputs beside their existing e-mail/phone fields. Keep the current field names, labels, and annual field semantics as specified.

- [x] **Step 4: Verify create/edit fields and labels**

Run with the same temporary Compose container and explicit `VALE_TEST_DATABASE_URL`, using `--reuse-db` and the listed navigation/form/label tests.

Expected: both entry forms expose the requested contact fields and all label tests pass.

- [x] **Step 5: Commit the template slice**

Do not make a separate commit yet; commit navigation, entry forms, consultation, deletion, and their focused tests together in Task 4 Step 5. Stage only the Vale navigation tuple hunk from the mixed context-processor changes.

### Task 4: Contact consultation and deletion screens

**Files:**
- Modify: `contatos/templates/contatos/prefeituras.html`
- Modify: `contatos/templates/contatos/prefeitura_excluir.html`
- Modify: `teste/test_vale_templates.py`
- Test: `teste/test_vale_navigation.py`

**Interfaces:**
- List and delete confirmation render the two contact blocks with name/e-mail/phone.
- The list omits unavailable Loja/Membro totals and GPRB expand/drill-down controls; deletion does not check external Loja relations.

- [x] **Step 1: Add failing consultation and deletion assertions**

Extend `teste/test_vale_templates.py` with `test_consult_lists_complete_contact_details` and `test_delete_confirmation_lists_complete_contact_details`. Assert the local contact values render and GPRB-only store/member counts, expand controls, and linked-store delete warnings are absent.

- [x] **Step 2: Run tests and verify RED**

Run with the same temporary Compose container and explicit `VALE_TEST_DATABASE_URL`, using `--reuse-db` and the consultation/delete tests.

Expected: contact details are not rendered in consultation/deletion, and the old external relationship markup remains.

- [x] **Step 3: Update the consultation and deletion templates**

Render Secretary/Treasury name, e-mail, and phone in `prefeituras.html` and `prefeitura_excluir.html`. Remove the unavailable Loja/Membro totals and drill-down, and delete only the local Vale without querying external relations. Preserve horizontal overflow behavior and existing routes.

- [x] **Step 4: Verify local contact display**

Run the complete focused Vale suite with the same temporary Compose container and explicit `VALE_TEST_DATABASE_URL`, using `--reuse-db`.

Expected: list and delete views show all saved contact details; no GPRB connector is called.

- [x] **Step 5: Commit the consultation/deletion slice**

Commit together with Task 3 as one Vale UI slice: the four Vale templates, navigation tuple hunk, and `test_vale_templates.py`, `test_vale_navigation.py`, `test_delegado_labels.py`, and `test_mensalidade_labels.py`. Do not stage the broad untracked `test_vale_labels.py` or unrelated context-processor changes.

### Task 5: Update architecture and database documentation

**Files:**
- Modify: `specs/legacy/database.md`
- Modify: `specs/legacy/architecture.md`
- Modify: `DOCS/README.md` (migration section only)

- [x] **Step 1: Document local Vale persistence**

Record that `vales` is a new, empty, tenant-scoped local table; the CRUD now uses Django ORM; no external rows or GPRB relationships were imported; unrelated GPRB-dependent workflows remain deferred. Document that the displayed Mensalidade label still maps to annual storage fields.

- [x] **Step 2: Review documentation diffs**

Run: `git diff --check -- specs/legacy/database.md specs/legacy/architecture.md DOCS/README.md`

Expected: clean scoped documentation changes. Preserve the broader in-progress README edits and stage only the Vale/migration paragraphs.

- [x] **Step 3: Commit the documentation slice**

Commit only the Vale-specific documentation hunks/files.

### Task 6: Back up, apply, and verify the local migration

**Files:**
- No additional application source changes; operate only on local Docker `saldabritanea` and `gprbr-app`.
- Backup: `C:\Users\mosan\AppData\Local\Temp\opencode\saldabritanea-before-vales-<timestamp>.dump` (never add to Git).

- [x] **Step 1: Preflight the active target and empty destination table**

Verify `gprbr-db` and `gprbr-app` are healthy, Django `current_database()` is `saldabritanea`, the existing named volume is mounted, and `to_regclass('public.vales')` is absent. If the table exists, stop and inspect; never drop or overwrite it. Confirm external `GPRB_DB_*` app environment names remain absent and `GPRB_DB_ENABLED=False` without printing secret values.

- [x] **Step 2: Back up the active Docker database before DDL**

Create and validate a custom-format dump of the active Docker target only. Run in PowerShell, using a unique timestamp and the verified local role `gprbr`:

```powershell
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$file = "saldabritanea-before-vales-$stamp.dump"
docker exec gprbr-db pg_dump -U gprbr -Fc -d saldabritanea -f "/tmp/$file"
docker cp "gprbr-db:/tmp/$file" "$env:LOCALAPPDATA\Temp\opencode\$file"
$backup = "$env:LOCALAPPDATA\Temp\opencode\$file"
if ((Get-Item $backup).Length -le 0) { throw 'Backup is empty' }
docker exec gprbr-db pg_restore --list "/tmp/$file" > $null
if ($LASTEXITCODE -ne 0) { throw 'Backup archive validation failed' }
```

Never dump Docker `gprbr` or connect to the external same-name instance for this task. Keep the host archive outside Git.

- [x] **Step 3: Apply only the application migration**

Run `docker compose build app`, then `docker compose up -d --no-deps app`. The application entrypoint runs `migrate`; if needed, run `docker exec gprbr-app python manage.py migrate --noinput`. Do not recreate `db`, change its volume, import external data, run `down -v`, or automatically drop/restore the target if a migration fails.

- [x] **Step 4: Verify the local schema and runtime**

Verify `showmigrations contatos` marks `0015_vale` applied, `public.vales` exists in `saldabritanea`, the application health endpoint returns 200, and the CRUD tests pass against `test_saldabritanea_vales`. Confirm the source `gprbr`, volume, and external connection restrictions remain unchanged.

## Deferred Problems

- The recorded `teste/test_fase_a_funil.py` baseline failures and full-suite timeout are outside this Vale data-model change; do not fix them here unless the user explicitly expands scope.
- GPRB-only Loja/Membro relations, counts, and their workflows remain deferred.

## Follow-up from read-only review

- The local Vale views must import only helpers already committed in `acesso.decorators`; writes enforce an explicit tenant in the Vale view, so clean checkouts do not depend on unrelated untracked tenant-context changes.
- The unselected SaaS role may read globally but cannot create, edit, or delete without an effective tenant. The regression suite covers all three writes.
- Edit contexts keep raw blank `prefeito`/`telefone` values; the list applies the `—` fallback only for display, preventing unrelated edits from persisting a placeholder as data.
- `pytest.ini` now defaults to the fail-closed test settings; GitHub Actions uses its isolated `gprbr_test` service URL, and the root README documents the Compose runner.
- The legacy `prefeitura_lojas_json` route remains as specified, but `GPRB_DB_ENABLED=False` is hard-coded and `core.gprb.connection.connect()` returns a dummy connection; the Vale screens no longer link to it.
- The existing Delegado email is not added to list/delete summaries: approved display scope requires complete Secretary/Treasury contacts, while the list already has the Delegado phone.
- Host test runs with ambient `localhost`/`postgres` settings are not valid evidence. Final Vale tests use the explicit Compose runner; unknown host test databases are not inspected or reset.
