# Potency Emulamentos PDF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow `admin_saas` to upload and replace one authenticated-viewable emulamentos PDF for each GPRB potency.

**Architecture:** Store one Django `PotenciaPdf` row per external GPRB `prefeitura.id`; generate the required filename from the potency name and current local year. Reuse the existing PDF validation limits, serve files through an authenticated inline endpoint, and enforce the `admin_saas` permission on both initial upload and replacement POSTs.

**Tech Stack:** Django 5.2, Django ORM/FileField, Django templates, GPRB repository, pytest-django.

**Spec:** `docs/superpowers/specs/2026-10-08-retire-tenant-roles-and-potency-pdf-design.md`

**Dependency:** Implement after the tenant-context and GPRB-context interfaces in
`2026-10-08-retire-tenant-roles-and-saas-admin.md` Tasks 2 and 5 are available.

## Global Constraints

- Only `admin_saas` may upload or replace a potency emulamentos PDF.
- `admin_saas` must select the local tenant with slug `gprb` before a
  tenant-scoped GPRB potency write; regular GPRB users use their persisted
  `gprb` tenant context.
- Every other signed-in profile may view the PDF.
- The PDF is optional when creating a potency; retain one current PDF per potency and delete the previous stored file after the new upload succeeds.
- Generate basename `{nome_da_potencia}_emulamentos_{ano_atual}.pdf`; sanitize path-invalid characters.
- Validate `.pdf` extension and `%PDF-` signature; reject files larger than 10 MiB.
- Use the external GPRB `prefeitura.id` as a string key; do not add a Django foreign key to that external database.
- Store the PDF outside public `MEDIA_ROOT` and serve it through a login-protected endpoint, not an unguarded media URL.

## Review Focus

- Potency names with path characters, trailing whitespace, and Unicode must produce a safe basename with the exact suffix; test in Task 1.
- A `.pdf` filename with non-PDF bytes, or PDF bytes with a non-`.pdf` extension, must be rejected; test in Task 1.
- A file of exactly 10 MiB is accepted and a file of 10 MiB + 1 byte is rejected; test in Task 1.
- Replacing a PDF in the same year must keep the expected basename and remove the previous stored file only after the replacement is saved; test in Task 1.
- The uploaded file must not be reachable from `/media/`; anonymous requests and non-`admin_saas` direct upload POSTs must not access/replace it; test in Task 3.

---

### Task 1: Add the unique potency PDF model and safe storage service

**Files:**
- Modify: `contatos/models.py`
- Create: `contatos/private_storage.py`
- Create: `contatos/migrations/0015_potencia_pdf.py` (after the current `0014_lojapdf.py`)
- Create: `contatos/potencia_pdf.py`
- Modify: `core/settings.py`
- Modify: `docker-compose.yml`
- Modify: `.gitignore`
- Modify: `.dockerignore`
- Test: `teste/test_potencia_pdf.py`

**Interfaces:**
- Produces `PotenciaPdf` with unique `prefeitura_id: str`, `arquivo: FileField`, and `atualizado_em`.
- Produces `validar_pdf(arquivo) -> str | None`, returning the existing-compatible keys `arquivo`, `invalido`, or `tamanho`.
- Produces `nome_arquivo_emulamentos(nome_potencia: str, ano: int) -> str`.
- Produces `salvar_pdf_emulamentos(prefeitura_id: str, nome_potencia: str, arquivo) -> PotenciaPdf`.

- [ ] **Step 1: Write model, naming, validation, and replacement tests**

Add tests for uniqueness by potency ID; generated name with Unicode/path
characters sanitized; suffix `_emulamentos_{timezone.localdate().year}.pdf`; missing file;
extension/header mismatches; exact 10 MiB acceptance; 10 MiB + 1 byte rejection;
successful replacement; and old-file cleanup only after the replacement is
saved. Assert the private storage location is outside `MEDIA_ROOT` and does not
produce a public media URL.

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `pytest -q teste/test_potencia_pdf.py`

Expected: failures because the model, naming/validation helpers, and storage
service do not exist.

- [ ] **Step 3: Implement the model and migration**

Add `PotenciaPdf` with table name `potencia_pdf`, unique string
`prefeitura_id`, and a callable `upload_to` that places each replacement in a
unique potency-specific directory while preserving the generated basename.
Configure its storage in `contatos/private_storage.py` with
`location=settings.PRIVATE_MEDIA_ROOT` and `base_url=None`; set
`PRIVATE_MEDIA_ROOT = BASE_DIR / 'private_media'`. Add a Docker bind mount for
`./private_media:/app/private_media`, and ignore the private storage directory
in Git and the Docker build context. Generate migration `0015_potencia_pdf.py`.

- [ ] **Step 4: Implement naming, validation, and replacement storage**

In `contatos/potencia_pdf.py`, use `timezone.localdate().year` at the call site
for the current year, preserve valid Unicode in the potency name, replace
path-invalid characters, and trim trailing dots/spaces. Validate the new file
before touching the existing row. Save the new file and row first, then delete
the old stored path; clean up the new path if the database update fails.

- [ ] **Step 5: Run the focused tests and verify they pass**

Run: `pytest -q teste/test_potencia_pdf.py`

Expected: PASS; each potency has one row, the basename is correct, and failed
replacement does not delete the previous file.

---

### Task 2: Add optional upload to the new-potency form

**Files:**
- Modify: `repositories/gprb_repository.py`
- Modify: `contatos/views/gprb_prefeituras.py`
- Modify: `contatos/templates/contatos/prefeitura_nova.html`
- Test: `teste/test_prefeitura_emulamentos_web.py`

**Interfaces:**
- `repo.criar_prefeitura(dados) -> str | None` returns the UUID inserted into the external GPRB `prefeitura.id` column, or `None` when the GPRB tenant cannot be resolved.
- Consumes: `resolve_tenant_id(request)` and `web_requer_gprb_context(view_func)` from the SaaS tenant-administration plan.
- The form field is named `pdf`; it is offered to `admin_saas` only in the selected local `gprb` context. The view rejects a PDF upload attempt from another profile or a wrong/missing tenant context before creating a potency.

- [ ] **Step 1: Write initial-upload and create-result tests**

Add tests that repository creation returns the inserted ID; an `admin_saas`
POST with a valid PDF creates the potency and its matching `PotenciaPdf`; a
POST without a PDF still creates the potency; an invalid PDF creates no
potency; and a non-`admin_saas` request cannot create a potency by smuggling a
PDF field. An `admin_saas` request with no tenant selected or with a non-`gprb`
tenant selected cannot write to the external GPRB database. If storage fails
after GPRB potency creation, assert the response identifies the created
potency's PDF page so the admin can retry without duplicating the potency.

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `pytest -q teste/test_prefeitura_emulamentos_web.py -k "nova or criar_prefeitura"`

Expected: failures because the repository does not return its ID and the form
does not accept/store a file.

- [ ] **Step 3: Return the external potency ID from the repository**

Generate the UUID into a local variable before the `INSERT` in
`repo.criar_prefeitura`, pass that value into the SQL parameters, and return it
after a successful transaction. Preserve `None` when no GPRB tenant is
available.

- [ ] **Step 4: Implement the multipart create flow**

Set `enctype="multipart/form-data"` and render the optional PDF field only
when `web_usuario.role == 'admin_saas'` and the selected local tenant is
`gprb`; when SaaS admin has no GPRB context, show a prompt to select it and do
not offer the PDF input or submit action. Enforce `web_requer_gprb_context` on
the mutation, reject a PDF field for other roles; validate an admin upload
before inserting the potency;
then associate the file using the returned external ID and potency name. If
file storage fails after the potency was created, redirect to its PDF page with
a clear retry message rather than resubmitting the potency form.

- [ ] **Step 5: Run initial-upload tests and existing potency tests**

Run: `pytest -q teste/test_prefeitura_emulamentos_web.py teste/test_gprb_writes.py`

Expected: PASS; potency creation still works without a file and the PDF is
attached to the exact ID inserted in the GPRB database.

---

### Task 3: Add authenticated PDF view/replacement page and list action

**Files:**
- Create: `contatos/views/prefeitura_pdf.py`
- Create: `contatos/templates/contatos/prefeitura_emulamentos.html`
- Modify: `contatos/views/__init__.py`
- Modify: `contatos/urls.py`
- Modify: `contatos/templates/contatos/prefeituras.html`
- Test: `teste/test_prefeitura_emulamentos_web.py`

**Interfaces:**
- GET `prefeitura_emulamentos(request, pk)` renders the potency name and optional embedded PDF for any authenticated user; it shows the upload form only for `admin_saas` with local tenant `gprb` selected.
- GET `prefeitura_emulamentos_arquivo(request, pk)` serves `FileResponse` with `application/pdf` and inline disposition after login and potency lookup.
- POST `prefeitura_emulamentos_upload(request, pk)` requires `web_requer_gprb_context`, validates `admin_saas`, potency, and PDF, then calls `salvar_pdf_emulamentos`.

- [ ] **Step 1: Write authentication, visualization, and role-matrix tests**

Add tests for anonymous redirects on the page and file endpoint; any signed-in
role can view the page/PDF; non-`admin_saas` templates omit the upload control;
the private file path is not accessible through `/media/`; direct non-`admin_saas`
POST and `admin_saas` POSTs with a missing/wrong GPRB tenant context are denied
without changing the existing file; `admin_saas` can upload/replace when the
`gprb` tenant is selected; a missing potency returns 404; and the list
shows a **Visualizar** action even when the PDF is absent.

- [ ] **Step 2: Run the focused web tests and verify they fail**

Run: `pytest -q teste/test_prefeitura_emulamentos_web.py`

Expected: failures because the PDF routes, page, upload enforcement, and list
action do not exist.

- [ ] **Step 3: Implement the authenticated page, stream, and upload route**

Register named routes under `contatos/urls.py` and re-export the views from
`contatos/views/__init__.py`. Require `web_login_required` for the page and
stream, and perform a distinct `request` role check for `ROLE_ADMIN_SAAS` on
the upload POST. Use `FileResponse` for the PDF so the underlying media URL is
not exposed in the page.

- [ ] **Step 4: Add the PDF page and action-column link**

Render the PDF inline through the protected stream route. Show an empty state
when no file exists. Render the replacement form only for `admin_saas` with
local tenant `gprb` selected; for SaaS admins without that context, show a
prompt to select the GPRB tenant. Add a **Visualizar** link in each potency
action cell targeting the named PDF page route.

- [ ] **Step 5: Run all PDF web tests and Django checks**

Run: `pytest -q teste/test_prefeitura_emulamentos_web.py teste/test_potencia_pdf.py`

Expected: PASS for initial upload, view, direct POST denial, replacement, and
storage cleanup.

Run: `python manage.py check`

Expected: `System check identified no issues`.

Run: `python manage.py makemigrations --check --dry-run`

Expected: no model changes remain unrepresented by migrations.
