# Isolamento de tenants por Vale — Plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provisionar um tenant por Vale e tornar locais e isolados os fluxos de Loja, Membro e candidatura, sem importar dados do GPRB.

**Architecture:** A criação do Vale provisiona Tenant e Vale atomicamente usando uma sigla obrigatória e única. Loja, Membro, PDF e Candidato passam a referenciar dados locais com FK de tenant; as views deixam de consultar o repositório GPRB nesses fluxos. O `admin_saas` segue sem tenant próprio, cria Vales globalmente e seleciona o tenant recém-criado; arquivamento preserva todos os dados.

**Tech Stack:** Django 5.2, PostgreSQL 15, Django ORM/migrations, pytest-django, templates Django/Tailwind, Docker Compose.

**Spec:** `DOCS/superpowers/specs/2026-10-11-vale-tenant-isolation-design.md`

## Global Constraints

- **“Um Vale corresponde a exatamente um tenant.”** Tenant pode existir sem Vale por compatibilidade, mas não possuir mais de um Vale.
- **“Sigla obrigatória e única.”** Nome visível do tenant e base de seu slug; colisões não criam tenant órfão.
- **“Provisionamento atômico.”** Tenant e Vale são criados na mesma transação.
- **“Lojas e Membros locais.”** Sem importar dados do GPRB.
- **“Candidaturas locais.”** Candidato iniciado vira Membro no mesmo tenant.
- **“Arquivamento seguro.”** Inativar Vale; preservar tenant, contas, registros e arquivos.
- **“Nenhuma conexão/importação GPRB.”** Manter `GPRB_DB_ENABLED=False`; não consultar nem alterar a instância externa.
- **“Tenants existentes preservados.”** Não converter, renomear nem excluir os três tenants atuais.
- Aplicar migrations somente a `saldabritanea`, após preflight e backup custom-format validado fora do Git. Nunca tocar `gprbr`, `esfera-postgres` ou `esferasda`; nunca executar `docker compose down -v`.
- Testes de ORM usam exclusivamente o banco isolado `test_saldabritanea_vales` via `core.settings_vale_test` e URL Docker explícita; nunca usar PostgreSQL ambiente do host nem resetar bancos fora desse DB de teste.
- Preservar alterações já existentes no workspace. Em arquivos modificados, revisar diffs e stagear somente hunks desta feature.
- `acesso/tenant_context.py`, `acesso/views/tenant_context.py` e `candidatos/migrations/0004_rename_candidato_tenant_status_idx_candidato_tenant__ef0372_idx.py` estão como alterações não rastreadas do usuário. Não editar, stagear, commitar ou descartar esses arquivos como parte desta feature. Integrar com `resolve_tenant_id(request)`, `tenant_id_da_sessao(request)` e a chave `admin_tenant_id` existentes. A migration de Candidato precisa de uma base de migrations versionada; se o `0004` continuar sem versionamento, parar antes de gerar uma migration dependente e pedir que o usuário o versione separadamente.

## Review Focus

- Sigla vazia, composta só por caracteres que `slugify` remove, ou que colide após normalização: formulário dá erro claro e não deixa Tenant órfão; cobrir em `teste/test_vale_provisioning.py`.
- Usuário forja tenant ou envia ID de Loja de outro Vale: retornar erro sem revelar nem alterar objeto; cobrir nos testes locais de Loja, Membro e Candidato.
- `admin_saas` está em “Todos os tenants” ou tem sessão selecionada inválida: não usar fallback `tenant_gprb()`; escrita falha fechada, exceto criar um novo Vale; cobrir em `teste/test_vale_provisioning.py` e `teste/test_candidate_local_flow.py`.
- Vale arquivado com sessão antiga: usuário comum não acessa rotas de operação e nenhum dado relacionado é removido; cobrir em `teste/test_vale_archive.py`.
- Duas tentativas de iniciar o mesmo candidato ou CPF já usado no tenant: no máximo um Membro é criado e estado/dados permanecem consistentes; cobrir em `teste/test_candidate_local_flow.py`.

---

### Task 1: Provisionamento e arquivamento de Vale

**Files:**
- Create: `contatos/vale_services.py`
- Modify: `contatos/models.py` (`Vale`)
- Modify: `contatos/views/vales.py`
- Modify: `contatos/views/__init__.py`
- Modify: `contatos/urls.py`
- Modify: `acesso/context_processors.py` (filter archived Vale tenants only; preserve all other existing edits)
- Modify: `contatos/templates/contatos/prefeitura_nova.html`
- Modify: `contatos/templates/contatos/prefeitura_editar.html`
- Modify: `contatos/templates/contatos/prefeituras.html`
- Modify: `contatos/templates/contatos/prefeitura_excluir.html`
- Create: `contatos/migrations/0016_vale_tenant_identity.py`
- Create: `teste/test_vale_provisioning.py`
- Create: `teste/test_vale_archive.py`
- Modify: `teste/test_potencia_web.py` (replace the old unselected-admin denial expectation)
- Modify: `teste/test_vale_local.py` and `teste/test_vale_templates.py` (supply required unique siglas; create form uses admin SaaS)

**Interfaces:**
- Produces `provisionar_vale(dados: dict[str, str]) -> Vale` in `contatos/vale_services.py`.
- The service creates `Tenant(nome=sigla, slug=slugify(sigla))` and `Vale(tenant=tenant, sigla=sigla, ...)` in one `transaction.atomic()` block; blank/duplicate/empty-normalized siglas raise a validation error.
- `Vale.tenant` becomes one-to-one; `Vale.sigla` becomes required and unique.
- Editing the Vale sigla synchronizes `Tenant.nome` but leaves the already-issued `Tenant.slug` unchanged.
- Creating Vale is restricted to `admin_saas`, requires no preselected tenant, and stores the new ID in session key `admin_tenant_id` only after a successful transaction.
- Existing Vale delete route archives by setting `status='INATIVA'`; add a reactivation route restricted to `admin_saas`.
- The reactivation endpoint is `contatos:prefeitura_reativar` at `prefeitura/<str:pk>/reativar/`.

- [x] **Step 1: Write failing provisioning and archive tests**

Add tests for: admin SaaS creation with no selected tenant; tenant name/slug from sigla; session auto-selection; blank, duplicate, overlength, and slug-empty siglas; rollback without orphan Tenant; one Vale per Tenant; editing sigla syncs Tenant.name but preserves Tenant.slug; duplicate edit sigla is rejected without changing either record; archive preserving Tenant and a tenant User; archived writes blocked; reactivation restoring access.

- [x] **Step 2: Run tests to verify failure**

Run the focused files using the safe Compose test runner from Global Constraints with `--create-db`.

Expected: tests fail because Vale still requires a manually selected Tenant, sigla is optional, and delete is physical.

- [x] **Step 3: Implement the provisioning service and model constraints**

Implement the declared service in `contatos/vale_services.py`; update Vale relation and sigla constraints; generate `0016_vale_tenant_identity.py`. Do not create `contatos/services/`, because `contatos/services.py` is an existing shared module. Keep Tenant identity tenantless for `admin_saas`; do not add an FK from the user to the newly created Tenant.

- [x] **Step 4: Implement the view/session and archive flows**

Allow only `admin_saas` to create a Vale without existing context, select the new tenant after successful save, and replace physical deletion with idempotent archive/reactivation. Hide inactive Vales from normal operation selectors and fail closed for stale selected sessions.

- [x] **Step 5: Run focused tests and Django checks**

Run `teste/test_vale_provisioning.py teste/test_vale_archive.py teste/test_potencia_web.py` in the isolated Compose test DB, then run `python manage.py check` in the app container.

Expected: all focused tests pass; the three existing Tenant rows and zero-Vale state are unaffected by test setup/teardown.

---

### Task 2: Modelos locais de Loja, Membro e PDF

**Files:**
- Modify: `contatos/models.py`
- Create: `contatos/migrations/0017_loja_membro_locais.py`
- Create: `contatos/migrations/0018_loja_pdf_required.py`
- Create: `teste/test_loja_membro_models.py`

**Interfaces:**
- Produces `Loja.tenant`, with local fields matching the current forms: `nome`, `numero`, `telefone`, `email`, `cidade`, `uf`, `endereco`, `secretario_nome`, `secretario_telefone`, `tesoureiro_nome`, `tesoureiro_telefone`, `mensalidade`, `situacao`, and timestamps. `Loja.deputado_mestre` is an optional FK to Membro; if set, that Membro must be associated with this Loja and tenant.
- Produces `Membro.tenant`, with fields matching current form names: `nome`, `cpf`, `situacao`, `rito`, `cadastro_maconico`, `tipo_admissao`, `data_admissao`, `escolaridade`, `data_iniciacao`, `potencia`, `cargo`, `condicao`, `data_nascimento`, `nacionalidade`, `naturalidade`, `estado_civil`, `pai`, `mae`, `identidade`, `orgao_emissor`, `data_emissao`, `email`, `celular`, `telefone_urgencia`, `endereco`, `numero`, `complemento`, `bairro`, `cidade`, `uf`, `cep`, `apresentacao_mx`, `apresentacao_ec`, `armadura_cbcs`, `data_passagem`, `data_elevacao`, `data_instalacao`, status and timestamps.
- Uses local tables `lojas` and `membros`; keeps the existing `loja_pdf` table name.
- Produces `Membro.lojas`, a many-to-many relation to local Loja; empty association is allowed. CPF is conditionally unique per tenant. Validate the president/Membro FK and M2M membership together.
- Changes `LojaPdf.loja_id` string to a non-null one-to-one FK to local `Loja`; preserves PDF upload behavior and the 10 MB limit.

- [x] **Step 1: Write failing model and relationship tests**

Test Loja/Membro registration, tenant FKs, CPF uniqueness per tenant, same CPF in different tenants, Membro with no Loja, multiple same-tenant Lojas, Loja.deputado_mestre relation, and PDF uniqueness per Loja. Cross-tenant M2M rejection is tested at the form/service boundary in Task 4.

- [x] **Step 2: Run tests to verify failure**

Run `teste/test_loja_membro_models.py` in the isolated Compose test DB with `--create-db`.

Expected: model imports or asserted fields/relations are missing.

- [x] **Step 3: Implement local models and migration**

Add Loja and Membro models with direct Tenant FKs and a conditional unique constraint on nonblank `(tenant, cpf)`. Generate `0017_loja_membro_locais.py` with the new LojaPdf FK nullable only during the schema transition, then `0018_loja_pdf_required.py` to enforce non-null after the old string column is removed. The active DB preflight must still confirm zero LojaPdf rows; never assign a fake default or infer a local Loja from an external ID. Keep local M2M validation at the service/form boundary. Do not apply either migration to the active DB in this task.

- [x] **Step 4: Run model tests and migration drift check**

Run the model test file and `python manage.py makemigrations --check --dry-run` using the safe settings.

Expected: tests pass and no model changes remain ungenerated.

---

### Task 3: CRUD local de Loja e PDF

**Files:**
- Modify: `contatos/views/gprb_lojas.py`
- Modify: `contatos/urls.py`
- Modify: `contatos/templates/contatos/lojas.html`
- Modify: `contatos/templates/contatos/loja_nova.html`
- Modify: `contatos/templates/contatos/loja_editar.html`
- Modify: `contatos/templates/contatos/loja_detalhe.html`
- Modify: `contatos/templates/contatos/loja_excluir.html`
- Create: `teste/test_loja_local.py`
- Create: `teste/test_loja_pdf_local.py`

**Interfaces:**
- All Loja routes use ORM querysets scoped by `tenant_id_da_sessao(request)`; create derives tenant from session, not POST.
- The active tenant's one Vale is displayed in the form; the user cannot select another Vale for a Loja.
- `loja_membros_json` returns only local members attached to the same-tenant Loja.
- PDF upload/delete resolves the Loja through the selected tenant before touching `LojaPdf` or its file.

- [x] **Step 1: Write failing local Loja/PDF view tests**

Cover create/list/search/detail/edit, cross-tenant GET/POST as 404, missing tenant, deletion blocked when members exist, deleting an empty Loja removes its local PDF file, tenant-safe member JSON, malicious member names rendered as text (never interpolated into an HTML sink), PDF upload/replacement/removal, invalid PDF, and over-10-MB PDF.

- [x] **Step 2: Run tests to verify failure**

Run `teste/test_loja_local.py teste/test_loja_pdf_local.py` in the isolated test DB.

Expected: routed views still call the GPRB repository or local model APIs are absent.

- [x] **Step 3: Replace GPRB repository calls in Loja views**

Implement ORM reads/writes and tenant-scoped object resolution; preserve current URLs and form field names. Render drill-down JSON values with DOM `textContent`, not string interpolation into `innerHTML`. Keep the legacy `prefeitura_lojas_json` endpoint separate and do not re-enable GPRB.

- [x] **Step 4: Bind PDFs to local Loja and update templates**

Use local Loja FK for upload/detail/delete; display the active Vale and preserve the current validation/error behavior.

- [x] **Step 5: Run local Loja/PDF tests**

Run the two focused files in the isolated test DB.

Expected: all CRUD, isolation, and PDF tests pass without calling `gprb_repository.connect`.

---

### Task 4: CRUD local de Membro

**Files:**
- Modify: `contatos/views/gprb_membros.py`
- Modify: `contatos/views/crud.py` (member list only)
- Modify: `contatos/urls.py`
- Create: `contatos/templates/contatos/membro_novo.html`
- Modify: `contatos/templates/contatos/lista.html`
- Modify: `contatos/templates/contatos/membro_editar.html`
- Modify: `contatos/templates/contatos/membro_detalhe.html`
- Modify: `contatos/templates/contatos/membro_excluir.html`
- Create: `teste/test_membro_local.py`

**Interfaces:**
- Adds `contatos:membro_novo`; existing list/detail/edit/delete routes use local Membro records.
- The manual create route is `membro/novo/` and is registered before `membro/<str:pk>/` to avoid resolving `novo` as an ID.
- Member list filters and pagination query only the selected tenant. Do not fabricate GPRB attendance/annuity history; omit those columns/filters until their local source is approved.
- Forms accept Loja IDs only from the same tenant. A Membro may have zero or several Lojas.

- [ ] **Step 1: Write failing member CRUD/isolation tests**

Cover create/read/edit/delete or inactivate, list filters, data round-trip for current editable fields, same-tenant multi-Loja association, empty association, cross-tenant rejection, CPF uniqueness per tenant, and no GPRB connector calls.

- [ ] **Step 2: Run tests to verify failure**

Run `teste/test_membro_local.py` in the isolated test DB.

Expected: current views still read/write through GPRB and there is no manual local create route.

- [ ] **Step 3: Implement tenant-scoped Membro CRUD**

Replace GPRB repository operations in the member list/detail/edit/delete views with ORM operations; add the manual create view and URL. Preserve current field names and optional multi-Loja behavior.

- [ ] **Step 4: Update list/detail/forms without GPRB-only metrics**

Keep local member fields and filters. Remove or clearly mark historical presence/annuity values that have no local data source; do not render fake zeroes.

- [ ] **Step 5: Run Membro tests and checks**

Run `teste/test_membro_local.py` and the relevant template tests in the isolated DB.

Expected: operations remain tenant-scoped and all stored fields round-trip.

---

### Task 5: Candidaturas locais e conversão em Membro

**Files:**
- Modify: `candidatos/models.py`
- Create: `candidatos/migrations/0005_candidato_loja_local.py` (only after confirming/versioning the current migration graph prerequisite)
- Modify: `candidatos/views/crud.py`
- Modify: `candidatos/views/api.py`
- Modify: `candidatos/views/__init__.py`
- Modify: `candidatos/urls.py`
- Modify: `candidatos/oficialato.py`
- Modify: `candidatos/templates/candidatos/detalhe.html`
- Modify: `recepcao/views/helpers.py`
- Create: `candidatos/services/__init__.py`
- Create: `candidatos/services/membros.py`
- Modify: `recepcao/templates/recepcao/kanban.html`
- Create: `teste/test_candidate_local_flow.py`

**Interfaces:**
- `Candidato.tenant` remains authoritative. `Candidato.loja` becomes an FK to local Loja; the Vale is derived through the tenant's one-to-one Vale relation. Candidate migration depends on the versioned candidate head and `contatos.0018_loja_pdf_required`.
- Remove the legacy text `Candidato.prefeitura`; replace text `Candidato.loja` with the local FK. Add `membro = OneToOneField('contatos.Membro', null=True, blank=True, on_delete=SET_NULL, related_name='candidato')`, so retries cannot create a second member.
- Preserve `candidatos:api_prefeituras` and `candidatos:api_lojas_por_prefeitura` URLs, but implement both locally. Without a tenant, both return 403. With a tenant, the first returns `{"prefeituras": [{"id": <int>, "nome": <str>}]}` for its one Vale; the second returns `{"lojas": [{"id": <int>, "nome": <str>}]}` for its active local stores.
- The Loja endpoint derives tenant/Vale from session rather than trusting `prefeitura_id`; browser options submit local integer Loja IDs, never names.
- `iniciar_candidato_como_membro(candidato: Candidato) -> Membro` creates/links one local Membro atomically, copies approved candidate fields, and associates the selected local Loja.
- Map candidate values directly: `nome_completo→nome`, CPF, birth date, civil status, nationality, natural city, parents, identity/emitter/issue date, e-mail, mobile, emergency phone, address fields, and selected Loja. Keep member-only fields blank/default when the candidate has no matching input; do not infer admission dates or ritual data.
- Candidate creation and initiation fail closed when no valid tenant is selected; remove the `tenant_gprb()` fallback.

- [ ] **Step 1: Resolve migration prerequisite without touching user-owned files**

Inspect the currently untracked `candidatos.0004` and migration graph, and recheck that the local Candidate table remains empty before removing its legacy text fields. If `0004` remains unversioned or candidates exist, stop and ask the user to version/map them separately before creating `0005`; do not stage the untracked migration or discard candidate values.

- [ ] **Step 2: Write failing candidate/store/conversion tests**

Cover local Vale/Loja API options, no cross-tenant candidate-store binding, no tenant fallback, conversion to exactly one Membro, same-tenant association, duplicate CPF response, no automatic `Usuario` creation, and transaction rollback on conversion failure.

- [ ] **Step 3: Run tests to verify failure**

Run `teste/test_candidate_local_flow.py` in the isolated DB.

Expected: candidate API reads GPRB options and initiation has no verified local conversion path.

- [ ] **Step 4: Implement local candidate references and endpoints**

Replace text GPRB Vale/Loja selection with the active tenant's local Vale label and local Loja IDs. Validate tenant ownership server-side; update candidate detail/modal serializers to display the local Vale and Loja.

- [ ] **Step 5: Implement atomic candidate-to-member conversion**

Create `iniciar_candidato_como_membro`, persist `Candidato.membro`, and update candidate status in one transaction. Map `nome_completo→nome`, `cpf→cpf`, `data_nascimento→data_nascimento`, `estado_civil→estado_civil`, `nacionalidade→nacionalidade`, `natural_cidade→naturalidade`, `pai→pai`, `mae→mae`, `identidade_numero→identidade`, `orgao_emissor→orgao_emissor`, `data_emissao→data_emissao`, `email→email`, `celular→celular`, `telefone_urgencia→telefone_urgencia`, address fields to their same-purpose member fields, and the selected candidate Loja to `Membro.lojas`. Preserve defaults for member-only fields with no candidate equivalent. Preserve the current duplicate-CPF response and make repeated initiation idempotent.

- [ ] **Step 6: Run candidate flow tests and verify no external calls**

Run `teste/test_candidate_local_flow.py` and assert patched GPRB connection attempts fail the test.

Expected: candidate creation and conversion work using only local ORM data.

---

### Task 6: Integração, UI de contato e rollout seguro

**Files:**
- Modify: `contatos/templates/contatos/prefeituras.html` (Secretary/Treasury layout only)
- Modify: `teste/test_vale_templates.py`
- Modify: `teste/test_vale_archive.py`
- Test: `teste/test_potencia_web.py`
- Test: `teste/test_loja_local.py`
- Test: `teste/test_membro_local.py`
- Test: `teste/test_candidate_local_flow.py`

**Interfaces:**
- Vale list shows Secretary/Treasury name on one line and e-mail/phone together beneath, wrapping safely at narrow widths.
- Existing Vale/Loja/Membro URLs remain stable unless an added route is needed for create/reactivate.

- [ ] **Step 1: Add template assertions for contact layout and archive states**

Assert both names render above e-mail/phone, archiving preserves Tenant/User/Loja/Membro/Candidato/PDF rows, the archived state offers reactivation only to `admin_saas`, and no unavailable GPRB-only metrics are rendered as numbers.

- [ ] **Step 2: Run all focused suites and static checks**

Run focused Vale/Loja/Membro/Candidato tests in the isolated Compose test DB; then run `python manage.py check` and `python manage.py makemigrations --check --dry-run` with the safe configuration.

Expected: focused suites pass, no pending model migrations, no external GPRB call.

- [ ] **Step 3: Perform active-database preflight and backup**

Recheck app/db health, `current_database()`, mounted volume, and counts of Vales/Candidatos/LojaPdf. Create and validate a custom-format backup outside Git. If any relevant data appeared, stop before applying destructive or reinterpretive migration operations.

- [ ] **Step 4: Apply migrations and rebuild only the app**

Apply Django migrations to Docker `saldabritanea`, rebuild the app image, and restart only the app service without removing/recreating the database volume. Do not connect to the external GPRB instance.

- [ ] **Step 5: Verify production-like behavior and commit scoped changes**

Verify migration state, Django checks, `/healthz/`, Vale provisioning, tenant scoping, local CRUD, candidate conversion, archive/reactivate, and GPRB-disabled behavior. Stage only this feature's files/hunks; leave all unrelated pre-existing workspace changes unstaged.

---

## Safe Compose test command

Run from PowerShell at the repository root, using the one-off app container and the dedicated test database only:

```powershell
docker compose run --rm --no-deps -v "$($PWD.Path):/app" --entrypoint sh app -c 'VALE_TEST_DATABASE_URL="$DATABASE_URL" python -m pytest -o addopts= --ds=core.settings_vale_test --create-db <test-files> -q'
```

Replace `<test-files>` with the focused test paths for the task. Use `--create-db` only for the dedicated `test_saldabritanea_vales` database.
