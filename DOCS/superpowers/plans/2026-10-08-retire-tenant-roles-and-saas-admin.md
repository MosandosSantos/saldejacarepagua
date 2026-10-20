# Retire Tenant Roles and Delegate Tenant Administration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `admin_company` and `operacional`, migrate their current users and invitations to `viewer`, and let `admin_saas` administer one explicitly selected tenant at a time in the web app.

**Architecture:** Keep the SaaS admin's database identity tenantless and store a separately validated tenant selection in the browser session. Route tenant-scoped reads and writes through a shared effective-tenant resolver, reject tenant-scoped writes when no tenant is selected, and keep the current platform-wide API scope for `admin_saas`. Migrate retired CRM roles to `viewer` and change GPRB role mapping so retired roles cannot return at login.

**Tech Stack:** Django 5.2, Django ORM and migrations, Django sessions and templates, FastAPI/Pydantic API, pytest-django.

**Spec:** `docs/superpowers/specs/2026-10-08-retire-tenant-roles-and-potency-pdf-design.md`

## Global Constraints

- `admin_company` and `operacional` are removed from supported CRM roles.
- Existing users and pending invitations with either role are converted to `viewer`; accounts, invitations, tenant records, and tenant ownership references are preserved.
- GPRB `ADMIN_LOJA`, `OPERADOR`, `MEMBER`, and unknown roles map to CRM `viewer`; `SYS_ADMIN` and official-role mappings stay unchanged.
- Other CRM roles and their current permissions remain unchanged.
- `admin_saas` has no tenant on its user record; its selected tenant is separate session context.
- Without a selected tenant, web tenant-scoped reads remain global and read-only; tenant-scoped writes require a valid selection.
- The API retains the established platform-wide `admin_saas` scope and authenticates authorization against the current database user.

## Review Focus

- Existing users and pending invitations with either retired role must retain their records and become `viewer`; pin this in the migration test in Task 1.
- Existing browser sessions and API tokens must use the user's migrated database role rather than stale authorization data; pin this in Task 1.
- A SaaS admin with no tenant selected must not create, update, or delete tenant-scoped records; pin representative POST checks in Task 5.
- A forged, deleted, or changed selected tenant must never expose or mutate another tenant's data; pin this in Tasks 2, 4, and 5.
- A former `admin_company` tenant owner must retain the owner reference, while transfers are authorized only by `admin_saas` in the selected tenant; pin this in Task 3.

---

### Task 1: Remove tenant roles and migrate existing identities

**Files:**
- Modify: `acesso/models.py`
- Modify: `acesso/context_processors.py`
- Modify: `acesso/urls.py`
- Modify: `acesso/views/__init__.py`
- Modify: `acesso/views/helpers.py`
- Modify: `acesso/views/auth.py`
- Modify: `acesso/templates/acesso/convidar.html`
- Delete: `acesso/templates/acesso/onboarding.html`
- Modify: `api/v1/schemas/auth.py`
- Modify: `api/v1/services/usuario_service.py`
- Modify: `api/v1/services/contato_service.py`
- Create: `acesso/migrations/0019_retire_admin_company_operacional.py` (next after the current `0018` migration)
- Test: `teste/test_role_retirement_migration.py`
- Test: `teste/test_role_retirement.py`

**Interfaces:**
- Consumes: current role constants, `Usuario.role`, `Convite.papel`, and `_GPRB_ROLE_MAP`.
- Produces: no supported role choices or RBAC sets containing `admin_company` or `operacional`; `ROLES_DE_TENANT` contains only `ROLE_VIEWER`; removed/unknown GPRB roles map to `ROLE_VIEWER`; every `admin_saas` user record remains tenantless. Keep the two constants temporarily only until Task 3 replaces their remaining implementation references, then remove them.

- [ ] **Step 1: Write migration and role-contract tests**

Add tests:

- `test_migration_converts_retired_users_and_pending_invites_to_viewer`
- `test_removed_roles_are_not_assignable`
- `test_gprb_removed_and_unknown_roles_map_to_viewer`
- `test_existing_browser_session_uses_migrated_viewer_role`
- `test_existing_api_token_uses_migrated_viewer_role`
- `test_admin_company_onboarding_route_is_removed`
- `test_existing_admin_saas_tenant_is_cleared`
- `test_gprb_sys_admin_sync_remains_tenantless`

The migration test must also assert that usernames, tenant IDs, invitation
tokens, and tenant owner references are preserved. Use `MigrationExecutor` to create historical
`admin_company`/`operacional` users and pending invitations at migration
`0018`, plus an `admin_saas` record with a tenant, then migrate to `0019` and
assert the resulting database rows. Seed a browser session with a stale
retired-role snapshot and verify middleware refreshes it from the migrated row.

- [ ] **Step 2: Run tests and verify the expected failures**

Run: `pytest -q teste/test_role_retirement_migration.py teste/test_role_retirement.py`

Expected: failures show the current roles remain assignable/mapped and existing
records are not migrated.

- [ ] **Step 3: Implement role retirement and the data migration**

Remove the retired values from `ROLES`, `ROLES_DE_TENANT`,
`_ROLES_EDITAM_BASE`, `ROLES_GESTORES_USUARIOS`, `ROLES_ATRIB_CRIACAO`,
`ROLES_ADMINISTRATIVOS`, and `ROLE_LABELS`. Keep the two string constants
temporarily for still-unconverted implementation references. Add a data migration that changes
`Usuario.role` and pending `Convite.papel` values from either retired role to
`viewer`, then updates their model field choices. Update the GPRB map and its
unknown-role fallback to `ROLE_VIEWER`. Set `tenant_id` to null for all
`admin_saas` rows in the same data migration. In `entrar_com_usuario_gprb`, do
not associate `SYS_ADMIN`/`admin_saas` records with the GPRB tenant, and clear
an existing tenant when that external role synchronizes to `admin_saas`.
Remove the `admin_company` onboarding
redirect, view export, URL, and template. Remove role-label special cases from
the invitation acceptance template, and remove the retired values from API
`Role` and `UsuarioService` validation.

- [ ] **Step 4: Run tests and verify the migration/role contract**

Run: `pytest -q teste/test_role_retirement_migration.py teste/test_role_retirement.py teste/test_auth_api.py teste/test_login_web.py`

Expected: PASS; migrated accounts and invitations remain present with role
`viewer`, and API-created users cannot use either retired role.

---

### Task 2: Add validated SaaS tenant selection context

**Files:**
- Create: `acesso/tenant_context.py`
- Create: `acesso/views/tenant_context.py`
- Modify: `acesso/views/__init__.py`
- Modify: `acesso/urls.py`
- Modify: `acesso/context_processors.py`
- Modify: `acesso/decorators.py`
- Modify: `acesso/session.py`
- Modify: `core/utils.py`
- Modify: `templates/base/basic.html`
- Modify: `contatos/views/gprb_prefeituras.py`
- Modify: `contatos/views/gprb_lojas.py`
- Modify: `contatos/views/gprb_membros.py`
- Modify: `contatos/views/crud.py`
- Modify: `contatos/views/negocios.py`
- Modify: `contatos/views/campos.py`
- Modify: `contatos/views/carteiras.py`
- Modify: `contatos/views/importacao.py`
- Modify: `tarefas/views.py`
- Modify: `automacoes/views.py`
- Modify: `emails/views.py`
- Modify: `recepcao/views/kanban.py`
- Modify: `recepcao/views/atividades.py`
- Modify: `candidatos/views/crud.py`
- Test: `teste/test_saas_tenant_context.py`
- Test: `teste/test_saas_tenant_write_scope.py`

**Interfaces:**
- Produces `resolve_tenant_id(request) -> int | None`, using the persisted tenant for regular users and the validated session key `admin_tenant_id` for `admin_saas`.
- Produces POST view `selecionar_tenant_contexto(request)`, which accepts a tenant ID or an empty value to clear the selection; only `admin_saas` may change this context.
- Produces `web_requer_tenant_context(view_func)`, which blocks unsafe tenant-scoped web methods when `admin_saas` has no valid selection; safe read methods remain available.
- The SaaS selection must never be copied into `Usuario.tenant_id` or the identity snapshot `request.session['usuario']`.

- [ ] **Step 1: Write selection, validation, and tenant resolver tests**

Add `test_admin_saas_selects_and_clears_tenant_context`,
`test_selection_rejects_nonexistent_tenant`,
`test_deleted_selected_tenant_clears_context`,
`test_non_saas_user_cannot_change_tenant_context`, and
`test_resolver_ignores_selection_for_regular_user`. Assert that the persisted
`admin_saas.tenant_id` remains `None` after selection. In
`test_saas_tenant_write_scope.py`, add no-selection POST tests for contacts,
email models, tasks, automations, candidates, and GPRB-backed mutation routes;
assert no database changes occur while an unselected SaaS admin can still read
global tenant data. Add tests for overlong numeric tenant IDs in both POST form
input and a forged session value; reject/clear them without a 500.

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `pytest -q teste/test_saas_tenant_context.py teste/test_saas_tenant_write_scope.py`

Expected: failures because the selection endpoint, selector context, resolver,
large-input rejection, and tenant-write guard do not exist.

- [ ] **Step 3: Implement the resolver and POST selection endpoint**

Add a single resolver in `acesso/tenant_context.py`; parse and verify selected
IDs against `Tenant`, reject oversized numeric strings before integer
conversion, and clear invalid/deleted selections. Add a login-protected POST
route. Accept only same-site local `next` destinations when redirecting.
Update `core.utils.tenant_id`, `acesso.decorators.tenant_id_da_sessao`, and
`acesso.session.obter_tenant_id` to use the shared resolver instead of reading
the user snapshot directly.

- [ ] **Step 4: Add the SaaS selector to the authenticated shell**

Expose tenant options and the selected tenant name from `web_sessao` only for
`admin_saas`, then add a CSRF-protected selector form to
`templates/base/basic.html`. The form posts to the selection endpoint and has
an explicit option that clears the selection.

- [ ] **Step 5: Enforce read-only global context on tenant writes**

Implement `web_requer_tenant_context` as an unsafe-method guard for
`admin_saas` without a valid selected tenant. Apply it to tenant-scoped
mutations in the listed view modules. Keep read GETs global when no tenant is
selected; do not alter platform profile/password/theme actions or the existing
API platform-wide scope. GPRB writes with the wrong selected tenant receive
their more specific `gprb` guard in Task 5.

- [ ] **Step 6: Run context, write-guard, and existing access regressions**

Run: `pytest -q teste/test_saas_tenant_context.py teste/test_saas_tenant_write_scope.py teste/test_login_web.py`

Run: `pytest -q teste/test_rbac_web.py -k "viewer"`

Expected: PASS; regular-user tenant scope and login behavior are unchanged.
RBAC tests still using retired-role fixtures are updated in Task 6.

---

### Task 3: Delegate team, configuration, and ownership administration

**Files:**
- Modify: `acesso/views/helpers.py`
- Modify: `acesso/views/equipe.py`
- Modify: `acesso/views/config.py`
- Modify: `acesso/models.py`
- Modify: `acesso/context_processors.py`
- Modify: `acesso/templates/acesso/equipe_novo.html`
- Modify: `acesso/templates/acesso/equipe_editar.html`
- Modify: `acesso/templates/acesso/config.html`
- Test: `teste/test_saas_tenant_admin.py`

**Interfaces:**
- Consumes: `resolve_tenant_id(request)` from Task 2.
- Produces: `guard_equipe(request)` allows `admin_saas` only when a valid tenant is selected and preserves eligible official-role managers using their persisted tenant; configuration actions identify SaaS tenant administration by `role == ROLE_ADMIN_SAAS` and non-`None` resolved tenant ID.

- [ ] **Step 1: Write tests for team, settings, goals, and ownership under SaaS admin**

Add tests that an `admin_saas` with Tenant A selected can list/create tenant
users, invitations, edit tenant settings/goals, and transfer ownership within
Tenant A; assert Tenant B users/settings/owner are untouched. Add tests that no
selection blocks team/config/ownership writes and that a tampered tenant ID in
POST cannot select Tenant B. GPRB-database users are visible/editable only
while the selected local tenant is the existing `gprb` tenant; other tenant
selections must show only local users.

- [ ] **Step 2: Run the SaaS administration tests and verify they fail**

Run: `pytest -q teste/test_saas_tenant_admin.py`

Expected: current `guard_equipe` and config role checks reject the SaaS admin
or cannot resolve a selected tenant.

- [ ] **Step 3: Scope team listing and account management to the selected tenant**

Replace direct reads of `request.session['usuario']['tenant_id']` in
`acesso/views/equipe.py` and `guard_equipe` with `resolve_tenant_id(request)`.
Update `guard_equipe` to require a tenant context and an eligible manager
profile, and use that
context for local and GPRB-backed account queries and all create/edit/delete
operations. Load GPRB-database users only for the selected local `gprb` tenant;
other tenants list and edit only local users, so the fixed external GPRB source
cannot leak across tenants. Keep retired roles out of the account role options.

- [ ] **Step 4: Move company-only configuration actions to selected SaaS context**

Replace `ROLE_ADMIN_COMPANY` checks in `acesso/views/config.py` with the
selected-tenant SaaS-admin predicate for company settings, team invitations,
monthly goals, seller goals, and owner transfer. Resolve target tenants and
tenant settings from `resolve_tenant_id(request)` rather than `usuario.tenant`;
resolve owner candidates only inside the selected tenant. Keep personal profile,
password, theme, and session actions available under their existing rules.
Remove the temporary retired-role constants from `acesso/models.py` after all
production references have been replaced.

- [ ] **Step 5: Run SaaS administration, invitation, and RBAC tests**

Run: `pytest -q teste/test_saas_tenant_admin.py teste/test_equipe.py teste/test_ativacao_web.py teste/test_rbac_web.py`

Expected: PASS; SaaS admin can manage the selected tenant while viewer and
unselected SaaS requests cannot perform tenant administration.

---

### Task 4: Scope tenant-scoped reads to the selected tenant

**Files:**
- Modify: `dashboard/views.py`
- Modify: `emails/views.py`
- Test: `teste/test_saas_tenant_read_scope.py`

**Interfaces:**
- Consumes: `resolve_tenant_id(request)` from Task 2.
- Produces: all tenant-scoped web read views use the resolved tenant ID; `admin_saas` with no selection retains global read-only results, and with a selection sees only that tenant.

- [ ] **Step 1: Write no-selection and selected-tenant read tests**

Add checks that an unselected SaaS admin can read the existing global contact
and dashboard views; a selected Tenant A sees only A's contacts, tasks, email
models, and kanban data; and directly requesting a Tenant B record while A is
selected does not expose it. Verify regular-user queries remain tied to their
persisted tenant even if the session contains a forged SaaS selection.

- [ ] **Step 2: Run the focused read-scope tests and verify they fail**

Run: `pytest -q teste/test_saas_tenant_read_scope.py`

Expected: dashboard/email views that read `tenant_id` directly from the user
snapshot ignore the selected tenant, so one or more selected-tenant assertions
fail.

- [ ] **Step 3: Route remaining direct tenant reads through the resolver**

Replace direct `request.session['usuario']['tenant_id']` reads in
`dashboard/views.py` and `emails/views.py` with `resolve_tenant_id(request)`.
Keep module flows that already use `core.utils.tenant_id` or
`acesso.decorators.tenant_id_da_sessao`; those helpers now resolve the selected
tenant from Task 2.

- [ ] **Step 4: Run scope tests and existing tenant isolation tests**

Run: `pytest -q teste/test_saas_tenant_read_scope.py teste/test_dashboard_avancado.py teste/test_fase_f_pipeline.py teste/test_fase_o_email_avancado.py`

Expected: PASS; SaaS admin reads are global without selection and tenant-filtered
after selecting a tenant; regular-user scope is unchanged.

---

### Task 5: Bind external GPRB mutations to the GPRB tenant context

**Files:**
- Modify: `acesso/decorators.py`
- Modify: `contatos/views/gprb_prefeituras.py`
- Modify: `contatos/views/gprb_lojas.py`
- Modify: `contatos/views/gprb_membros.py`
- Test: `teste/test_saas_tenant_write_scope.py`

**Interfaces:**
- Consumes: `resolve_tenant_id(request)` and `web_requer_tenant_context(view_func)` from Task 2.
- Produces `web_requer_gprb_context(view_func)`, which permits GPRB mutations only for a regular user in local tenant `gprb` or an `admin_saas` with local tenant `gprb` selected.

- [ ] **Step 1: Write no-selection and cross-tenant write tests**

Add checks that `admin_saas` with Tenant Beta selected cannot mutate the fixed
external GPRB potency/store/member records; no selection remains blocked by the
Task 2 guard; and a user whose persisted tenant is `gprb` or an `admin_saas`
with local `gprb` selected can perform the existing authorized GPRB
mutations.

- [ ] **Step 2: Run the focused write-scope tests and verify they fail**

Run: `pytest -q teste/test_saas_tenant_write_scope.py -k "gprb"`

Expected: a SaaS admin selected into another tenant can still reach the fixed
external GPRB mutations, so the wrong-context assertions fail.

- [ ] **Step 3: Implement tenant and GPRB mutation guards**

Add `web_requer_gprb_context` to `acesso/decorators.py` and apply it to all
GPRB-backed potency, store, member, and PDF mutation routes. The guard must
resolve the effective local tenant and verify slug `gprb`; allow regular users
using their persisted `gprb` tenant and `admin_saas` only with `gprb` selected.
Gate unsafe HTTP methods while preserving read-only GET pages.

- [ ] **Step 4: Run write-scope tests and existing tenant isolation tests**

Run: `pytest -q teste/test_saas_tenant_write_scope.py -k "gprb"`

Expected: PASS; GPRB mutation routes cannot target external `GPRB` data while a
different local tenant is selected.

---

### Task 6: Update fixtures, tests, seeds, and current role documentation

**Files:**
- Modify: `teste/conftest.py`
- Modify: RBAC and feature tests under `teste/` that construct or assert the retired roles
- Modify: `contatos/management/commands/seed_dados.py`
- Modify: `README.md`
- Modify: `DOCS/README.md`
- Modify: `DOCS/PRD.md`
- Modify: `specs/legacy/requirements.md`
- Modify: `specs/legacy/business-rules.md`
- Modify: `specs/legacy/api.md`
- Modify: `specs/001-financeiro-anuidades/spec.md`
- Modify: `specs/005-problema-permissoes/spec.md`

**Interfaces:**
- All tests that need tenant administration authenticate as `admin_saas` and explicitly select their fixture tenant.
- Tests that represent former operational/admin-company accounts use `viewer` or the migration fixture; official-role tests remain unchanged.

- [ ] **Step 1: Inventory tests and seed/docs references to retired roles**

Run: `rg -l "admin_company|operacional|ROLE_ADMIN_COMPANY|ROLE_OPERACIONAL|headers_operacional|usuario_operacional" teste contatos/management/commands/seed_dados.py README.md DOCS specs`

Expected: the command lists every fixture, behavior test, seed, and current
role reference that needs migration or explicit historical context.

- [ ] **Step 2: Update test fixtures and expected access behavior**

Remove fixtures that create retired roles as current supported accounts. Add or
reuse a helper that logs in `admin_saas` and posts the selected tenant into the
context endpoint. Convert old write-allowed operational/admin-company
expectations to the approved model: `viewer` is read-only; selected
`admin_saas` administers tenants; official profiles keep their existing
behavior. Keep explicit migration tests that create historical role values.

- [ ] **Step 3: Update seeds and current documentation**

Remove retired roles from generated sample users. Update current role tables,
RBAC descriptions, and API docs to describe `admin_saas`, official roles, and
`viewer`. Mark completed specs that describe the previous role model as
historical/superseded rather than rewriting their original requirements.

- [ ] **Step 4: Run all affected role, web, API, and feature tests**

Run: `pytest -q teste/test_role_retirement_migration.py teste/test_role_retirement.py teste/test_saas_tenant_context.py teste/test_saas_tenant_admin.py teste/test_saas_tenant_read_scope.py teste/test_saas_tenant_write_scope.py teste/test_rbac_web.py teste/test_rbac_api.py teste/test_auth_api.py`

Expected: PASS.

- [ ] **Step 5: Run the complete project verification**

Run: `pytest -q`

Expected: all tests pass; no supported choices, current documentation, or
active role mappings contain `admin_company` or `operacional`.

Run: `python manage.py check`

Expected: `System check identified no issues`.

Run: `python manage.py makemigrations --check --dry-run`

Expected: no model changes remain unrepresented by migrations.
