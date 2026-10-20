# Retire tenant roles, delegate tenant administration, and add potency PDF

**Date:** 2026-10-08  
**Status:** Design approved in conversation; awaiting written-spec review.

## Goal

Retire the CRM roles `admin_company` and `operacional`, transfer tenant-level
administration to `admin_saas`, and add one replaceable PDF table of potency
emulamentos per GPRB potency. Existing users and pending invitations carrying
either retired role become `viewer`.

## Approved decisions

- Remove `admin_company` and `operacional` from supported CRM roles.
- Convert existing local users and pending invitations with either role to
  `viewer`; do not delete their accounts, invitations, or tenant records.
- Map GPRB authentication roles `ADMIN_LOJA`, `OPERADOR`, and `MEMBER` to
  `viewer` in this CRM. Unknown GPRB roles also fall back to `viewer`; keep
  `SYS_ADMIN` and official-role mappings unchanged.
- Keep all other CRM roles and their existing permissions unchanged.
- Give `admin_saas` the tenant administration functions currently assigned to
  `admin_company`, using an explicit selected-tenant context.
- Keep existing tenant ownership records. `admin_saas` can transfer ownership
  for the selected tenant.
- Only `admin_saas` may upload or replace a potency emulamentos PDF. Every other
  signed-in profile may view it.
- The potency PDF is optional when creating a potency. A single current PDF is
  retained per potency, and replacing it deletes the previous stored file.
- The requested filename suffix is spelled `emulamentos`:
  `{nome_da_potencia}_emulamentos_{ano_atual}.pdf`.

## Role retirement and data migration

Remove the two role values from model role choices, tenant-role/edit/admin
sets, user-management forms, invitation choices, API schemas, API user
creation validation, role labels, and any role-specific branches. Existing
users and pending invitations are updated by a data migration before the role
values are removed from the supported choices. Their other data remains
unchanged.

The GPRB-to-CRM role mapping must never recreate the retired roles. A local
user synchronized at login receives the mapped CRM role `viewer`. Existing
browser sessions already revalidate their role against the user row, and the
API resolves the current user from the database for each request; tests must
prove that old sessions/tokens no longer retain the retired permissions after
the migration.

The official profiles (Grande Prior, Grande Chanceler, Grande Tesoureiro,
Grande Secretário, Prefeito, and Deputado Mestre), `admin_saas`, and `viewer`
remain supported. The existing tenant owner reference is preserved even when
its user's role changes to `viewer`; tenant ownership transfer is performed by
`admin_saas` in the selected tenant context.

## SaaS admin tenant context

Add a tenant selector for `admin_saas` in the authenticated application shell.
The selection is stored separately from the SaaS admin's identity and does not
assign a tenant to the `Usuario` row. A server-side helper resolves the
effective tenant for tenant-scoped web operations:

- Regular tenant users continue to use their persisted tenant.
- `admin_saas` may select any existing tenant and then manage its users,
  invitations, settings, goals, ownership, and tenant-scoped CRM operations.
- The selected tenant is validated against the database and must not be
  accepted solely from a form or query parameter.
- Without a selected tenant, SaaS-wide screens remain global and read-only for
  tenant-scoped records. Tenant-scoped writes require a valid selection.
- Clearing or invalidating a selection returns SaaS admin pages to global
  read-only context.

All relevant list, detail, creation, update, deletion, invitation, settings,
and ownership-transfer flows must use the resolved tenant context consistently.
An operation must not silently widen a selected-tenant query to all tenants.
The existing API remains authenticated against the current database user and
retains the established `admin_saas` platform-wide scope; removed CRM roles
cannot be created or authorized through API role checks.

## Potency emulamentos PDF

Add a Django model for the PDF, keyed by the external GPRB `prefeitura.id`
(stored as a string rather than a Django foreign key). Enforce one database
record per potency. The storage path is partitioned by potency ID, with the
basename generated from the potency name, the literal `_emulamentos_`, and the
current local year. Sanitize path-invalid characters without exposing an
untrusted path.

Add an optional PDF input to `/contatos/prefeitura/nova/`, rendered and
accepted only for `admin_saas`. The GPRB repository's potency-creation result
must provide the created potency ID so the uploaded file can be associated
with it. Validate the upload before creating the potency; if file storage
fails after potency creation, report clearly that the potency exists and link
to its PDF page so the upload can be retried without creating a duplicate.

Add a PDF management/view page for each potency and a **Visualizar** action in
the potency list. The page displays the PDF inline for any authenticated user.
The file itself is served through an authenticated endpoint rather than an
unguarded media URL. Only `admin_saas` receives the replacement form, and the
upload endpoint independently enforces that permission. If no PDF exists,
show an empty state and the upload control only to `admin_saas`.

Reuse the established PDF validation behavior: `.pdf` extension, `%PDF-`
signature, and a 10 MiB maximum. Validate the new upload before replacing the
existing file; persist the replacement and remove the previous file only after
the new upload succeeds. No historical versions are retained.

## Acceptance criteria

1. `admin_company` and `operacional` are unavailable for new CRM accounts,
   edits, invitations, or API-created users.
2. Existing users and pending invitations with either role are converted to
   `viewer`; they can still authenticate but cannot perform writes reserved
   for the removed profiles.
3. External GPRB users mapped from `ADMIN_LOJA`, `OPERADOR`, and `MEMBER` enter
   as `viewer`; official-profile mappings are unchanged.
4. `admin_saas` can select a tenant and administer only that tenant in
   tenant-scoped web flows. With no selection, tenant-scoped web writes are
   blocked. Cross-tenant data cannot be changed by tampering with request
   parameters.
5. Tenant ownership data is preserved, and `admin_saas` can transfer ownership
   only within the selected tenant.
6. Creating a potency with a valid optional PDF stores the expected generated
   filename. Invalid or oversized PDFs are rejected with a clear message.
7. Replacing a potency PDF keeps exactly one row and one current stored file;
   the previous stored file is deleted only after successful replacement.
8. The potency list has a view action. Any authenticated profile can view the
   PDF; only `admin_saas` can upload or replace it, including by direct POST.

## Verification plan

- Test role-choice removal, local-user and pending-invitation data migration,
  and GPRB role mapping.
- Test that existing browser sessions and API tokens use the migrated
  database role rather than stale role values.
- Test SaaS tenant selection, selection clearing, no-selection write blocking,
  tenant isolation, team/invitation management, settings, goals, and ownership
  transfer.
- Test PDF creation, generated filename, PDF signature and size validation,
  replacement cleanup, authenticated inline viewing, and role-based upload
  denial.
- Run the focused access, API, tenant, and PDF tests, followed by the project
  test suite and Django checks.

## Scope boundaries

- Do not delete users, invitations, tenants, or tenant ownership records.
- Do not remove or rename official profiles.
- Do not introduce PDF history/versioning, multiple files per potency, or
  non-PDF document support.
- Do not change the platform-wide `admin_saas` scope of the existing API.
