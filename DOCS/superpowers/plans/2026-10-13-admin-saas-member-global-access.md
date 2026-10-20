# Admin SaaS Member Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `admin_saas` manage member records across tenants while keeping `ADM` and other tenant users scoped to their own tenant.

**Architecture:** Member queries become role-aware at the view boundary. `admin_saas` can read and mutate a member by its record ID without a selected header tenant, while every write derives the tenant from the member or an explicitly selected active Vale. Creation presents a target-Vale selector; posted store IDs remain server-validated against that Vale.

**Tech Stack:** Django 5.2.18, Django ORM, Django templates, pytest-django, PostgreSQL.

**Spec:** `DOCS/superpowers/specs/2026-10-13-admin-saas-member-access-design.md`

## Global Constraints

- `admin_saas` is tenantless; member CRUD must not write a synthetic tenant into the user identity or session.
- `admin_saas` member list/detail/edit/delete works across tenants without selecting a header tenant.
- Creating a member as `admin_saas` requires an explicit active Vale; the Vale's tenant is authoritative.
- `ADM` and other tenant roles remain scoped to the tenant associated with their account/session.
- Archived Vales and tenants without an active Vale are readable by `admin_saas` but do not accept member writes.
- Store IDs submitted for a member must belong to that member's tenant or selected Vale.
- Keep canonical `/membros/...` URLs and existing `/contatos/membro/...` aliases.
- Do not modify the `Tenant`, `Membro`, `Vale`, or `GrauMembro` schema; no migration is expected.
- Never query or mutate the external GPRB database.
- Preserve existing workspace changes; stage only the hunks/files for this feature.
- Run Django tests only with `core.settings_vale_test` and the isolated test database configured by `VALE_TEST_DATABASE_URL`; never use the app database as a test database.

## Review Focus

- `admin_saas` with no `admin_tenant_id` must still find members in multiple tenants; no fallback tenant may be invented.
- A selected tenant in the header must not leak into the Admin SaaS identity or cause a write to the wrong tenant.
- A tenant without a Vale or with an archived Vale permits historical read only; all member writes fail closed.
- A forged Vale or Loja ID in the create form must not create an orphan member or cross-tenant association.
- `ADM` with a missing tenant, archived/missing Vale, or a member/Loja from another tenant must remain blocked.

---

### Task 1: Role-aware member list and detail

**Files:**
- Modify: `contatos/views/crud.py` (`lista` tenant scope)
- Modify: `contatos/views/gprb_membros.py` (member-detail scope and optional Vale context)
- Test: `teste/test_membro_admin_saas.py`

**Interfaces:**
- Consumes: `ROLE_ADMIN_SAAS`, `tenant_id_da_sessao(request)`, local `Membro`, and `Vale`.
- Produces: Admin SaaS global member list/detail; tenant-scoped list/detail for `ADM` and all other tenant roles.
- For detail context, a member without a Vale gets a safe “sem Vale” representation rather than an exception.

- [ ] **Step 1: Write failing scope tests**

Add tests:
- `test_admin_saas_without_selection_lists_members_from_multiple_tenants`
- `test_admin_saas_without_selection_opens_member_in_another_tenant`
- `test_admin_saas_selected_header_context_still_lists_members_globally`
- `test_admin_saas_can_read_member_of_archived_or_no_vale_tenant`
- `test_adm_member_list_and_detail_are_scoped_to_account_tenant`
- `test_adm_cannot_access_members_when_its_vale_is_archived`
- `test_tenant_user_cannot_open_foreign_member`

Use real local tenants, Vales, members, and sessions. Assert response status and rendered member/tenant content; do not mock the queryset under test.

- [ ] **Step 2: Run the scope tests and verify the expected failures**

Run: `python -m pytest teste/test_membro_admin_saas.py -q --no-header -o addopts='' --create-db`

Expected: Admin SaaS detail without selection returns 403, and the current member list exposes a foreign tenant to `ADM`.

- [ ] **Step 3: Implement role-aware member list and detail**

In `contatos/views/crud.py`, only `ROLE_ADMIN_SAAS` receives the global member list; `ADM` uses its persisted tenant like other tenant roles. Tenant-scoped member routes require that tenant's active Vale. In `contatos/views/gprb_membros.py`, allow Admin SaaS global lookup by member ID regardless of header selection; keep tenant filtering for other roles. Make `_para_contexto_membro` handle a missing Vale without losing member/store labels.

- [ ] **Step 4: Run scope tests and verify they pass**

Run: `python -m pytest teste/test_membro_admin_saas.py -q --no-header -o addopts='' --reuse-db`

Expected: all global-read and tenant-isolation assertions pass.

### Task 2: Global Admin SaaS edits and deletes, tenant-safe writes

**Files:**
- Modify: `contatos/views/gprb_membros.py` (`membro_editar`, `membro_excluir`, shared member resolver)
- Test: `teste/test_membro_admin_saas.py`

**Interfaces:**
- Consumes: Task 1 member resolver and `_lojas_selecionadas(request, tenant_id)` validation.
- Produces: Admin SaaS edit/delete/inactivate by member ID across tenants without header selection; `ADM` and other roles remain own-tenant only.

- [ ] **Step 1: Add failing write-scope tests**

Add tests:
- `test_admin_saas_edits_member_without_selected_tenant`
- `test_admin_saas_edit_scope_is_global_even_when_header_tenant_is_selected`
- `test_admin_saas_can_inactivate_member_in_another_tenant`
- `test_admin_saas_cannot_edit_member_from_archived_vale`
- `test_admin_saas_rejects_loja_from_another_tenant`
- `test_adm_cannot_edit_or_delete_foreign_member`

Assert both response status and persisted state; cross-tenant Loja submissions must not change member relations.

- [ ] **Step 2: Run the write-scope tests and verify the expected failures**

Run: `python -m pytest teste/test_membro_admin_saas.py -k 'edits_member or edit_scope or inactivate_member or archived_vale or loja_from_another or foreign_member' -q --no-header -o addopts='' --reuse-db`

Expected: Admin SaaS writes without a selected header tenant are blocked by the current decorators/context lookup.

- [ ] **Step 3: Implement global Admin SaaS writes from the target member**

Remove the blanket header-context requirement from these member views and enforce scope in the member resolver: Admin SaaS targets the member's persisted tenant regardless of `admin_tenant_id`; other roles target only their account tenant. Require an active Vale for writes and keep `_lojas_selecionadas` bound to the member tenant.

- [ ] **Step 4: Run write-scope tests and verify they pass**

Run: `python -m pytest teste/test_membro_admin_saas.py -q --no-header -o addopts='' --reuse-db`

Expected: Admin SaaS can manage members globally, while foreign-tenant stores, ADM foreign members, and archived-Vale writes remain blocked.

### Task 3: Admin SaaS member creation with an explicit Vale target

**Files:**
- Modify: `contatos/views/gprb_membros.py` (`membro_novo` target resolution)
- Create: `contatos/templates/contatos/membro_novo.html`
- Test: `teste/test_membro_admin_saas.py`

**Interfaces:**
- Consumes: active Vales, Task 1/2 role scope, `_salvar_membro(request, vale, membro=None)`.
- Produces: a member-create form with an explicit Vale target for Admin SaaS; tenant and Loja associations are derived/validated server-side.

- [ ] **Step 1: Add failing create-form tests**

Add tests:
- `test_admin_saas_create_form_lists_active_vales_without_header_selection`
- `test_admin_saas_creates_member_in_selected_form_vale`
- `test_admin_saas_create_requires_active_vale_and_creates_no_orphan`
- `test_admin_saas_create_rejects_loja_from_another_vale`
- `test_adm_create_uses_only_its_account_tenant`

Use form field `vale_id` as the explicit Admin SaaS destination. When a header tenant is selected, the form may preselect that Vale, but the posted `vale_id` remains validated against an active Vale. Do not mutate `admin_tenant_id` during member creation.

Assert the new form renders, successful POST sets `Membro.tenant_id` from the selected Vale, and invalid Vale/Loja submissions create no records.

- [ ] **Step 2: Run create tests and verify the expected failures**

Run: `python -m pytest teste/test_membro_admin_saas.py -k 'create_form or creates_member or create_requires or create_rejects or create_uses' -q --no-header -o addopts='' --reuse-db`

Expected: Admin SaaS GET returns 403 without a header tenant and receives no form target selector; the current create template is also absent.

- [ ] **Step 3: Implement the create form and target-Vale validation**

Create `membro_novo.html` with the existing member field names and HAZON form styling. Admin SaaS chooses an active Vale in the form; show only its Loja choices and validate every posted Loja against the selected Vale's tenant. Other roles derive the Vale from their account tenant. Do not update `admin_tenant_id` during member creation.

- [ ] **Step 4: Run create tests and verify they pass**

Run: `python -m pytest teste/test_membro_admin_saas.py -q --no-header -o addopts='' --reuse-db`

Expected: global create succeeds only for a chosen active Vale; invalid and cross-tenant inputs fail without writes.

### Task 4: Final verification and container refresh

**Files:**
- Verify: `contatos/membros_urls.py`, `core/urls.py`, legacy aliases in `contatos/urls.py`
- Test: `teste/test_membros_urls.py`, `teste/test_membro_admin_saas.py`

**Interfaces:**
- Consumes: canonical member routes and the role-aware member CRUD from Tasks 1–3.
- Produces: verified `/membros/...` routes, old aliases still resolving, and an updated `app` container on port `8111`.

- [ ] **Step 1: Run focused member route and permission tests**

Run: `python -m pytest teste/test_membros_urls.py teste/test_membro_admin_saas.py -q --no-header -o addopts='' --reuse-db`

Expected: Admin SaaS global policy, ADM tenant isolation, and legacy URL aliases pass.

- [ ] **Step 2: Run Django system checks and migration drift check**

Run: `python manage.py check` and `python manage.py makemigrations --check --dry-run`.

Expected: no system-check issues and no new migrations.

- [ ] **Step 3: Rebuild only the app service**

Run: `docker compose up -d --build --no-deps app`.

Expected: app health check returns healthy; database and Redis containers are untouched.

- [ ] **Step 4: Confirm the container resolves both URL families**

Run `resolve('/membros/6/')` and `resolve('/contatos/membro/6/')` inside `gprbr-app`.

Expected: both route families resolve to `membro_detalhe`; canonical reverse resolves to `/membros/6/`.
