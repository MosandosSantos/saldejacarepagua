# SAL DA AMORIO Authentication and Email Branding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Use `superpowers:subagent-driven-development` only if the user explicitly chooses that approach.

**Goal:** Apply the `SAL DA AMORIO` brand to authentication screens, logout feedback, and system-generated email sender/signatures.

**Architecture:** Define `APP_BRAND_NAME` centrally and expose it to auth templates and email code. Force the configured display name on `DEFAULT_FROM_EMAIL` while preserving its current email address; keep user-authored campaign subjects and bodies unchanged.

**Tech Stack:** Django settings, Django messages framework, Django email backend, templates, pytest.

**Spec:** `DOCS/superpowers/specs/2026-10-10-amorio-tenant-navigation-brand-design.md`

## Global Constraints

- Brand text is exactly `SAL DA AMORIO`.
- Preserve the existing SMTP host, credentials, and from-address; change only the sender display name.
- Login/logout/activation and candidate notification messages use the approved brand; preserve the formal Grande Priorado name where it identifies the institution.
- Do not rewrite user-created email campaign subjects or bodies.
- Use `static/img/logow.webp` on login, activation, and the candidate invitation email.

## Review Focus

- `DEFAULT_FROM_EMAIL` supplied as a bare address: output still has display name `SAL DA AMORIO` and preserves the address; pin in `teste/test_branding_emails.py`.
- `DEFAULT_FROM_EMAIL` supplied with an old display name: replace only the display name; pin in the same test.
- Logout session flush followed by success messaging: login renders the confirmation; pin in `teste/test_login_web.py`.
- SMTP disabled/test backend: message construction remains testable without sending externally; use Django locmem email backend.
- User-authored campaign content: subject/body remain byte-for-byte unchanged while sender name changes; pin in `teste/test_branding_emails.py`.

---

### Task 1: Central brand setting and logout feedback

**Files:**
- Modify: `core/settings.py`
- Modify: `acesso/context_processors.py`
- Modify: `acesso/views/auth.py`
- Modify: `templates/base/basic.html`
- Modify: `acesso/templates/acesso/login.html`
- Modify: `acesso/templates/acesso/ativar.html`
- Test: `teste/test_login_web.py`

**Interfaces:**
- Add `settings.APP_BRAND_NAME = 'SAL DA AMORIO'`.
- Expose `APP_BRAND_NAME` to templates from `web_sessao`.
- `logout_web` posts a success message before redirecting to `acesso:login`.

- [ ] **Step 1: Write failing tests** `test_login_shows_amorio_brand`, `test_logout_shows_confirmation_after_session_flush`, and `test_logout_still_redirects_to_login`.
- [ ] **Step 2: Run** `python -m pytest teste/test_login_web.py -q`; expect missing brand/message assertions.
- [ ] **Step 3: Implement** the brand setting/context value, replace login and activation branding (including `logow.webp`), display Django messages in login, and add the logout success message after flushing the old session.
- [ ] **Step 4: Run** `python -m pytest teste/test_login_web.py -q`; expect all authentication tests to pass.

### Task 2: Apply the brand to system-generated emails

**Files:**
- Modify: `core/settings.py`
- Modify: `acesso/ativacao.py`
- Modify: `candidatos/views/emails.py`
- Modify: `candidatos/templates/candidatos/email_convite.html`
- Test: `teste/test_branding_emails.py`

**Interfaces:**
- All senders continue consuming `settings.DEFAULT_FROM_EMAIL`.
- Email activation and candidate-notification builders consume `settings.APP_BRAND_NAME`.

- [ ] **Step 1: Write failing locmem-backend tests** `test_default_sender_uses_amorio_and_preserves_address`, `test_activation_email_uses_amorio_brand`, `test_candidate_email_uses_amorio_signature_and_logo`, and `test_campaign_body_is_unchanged`.
- [ ] **Step 2: Run** `python -m pytest teste/test_branding_emails.py -q`; expect the existing `GPRBRCRM`/`SAL do RER` output and logo to fail assertions.
- [ ] **Step 3: Format** `DEFAULT_FROM_EMAIL` with `APP_BRAND_NAME` while preserving the configured address; update activation and candidate notification copy and use `logow.webp` in the HTML invitation. Do not alter user-authored campaign data.
- [ ] **Step 4: Run** `python -m pytest teste/test_branding_emails.py teste/test_fase_e_export_email.py teste/test_fase_o_email_avancado.py -q`; expect focused email tests to pass.

### Task 3: Integrated verification and container cutover

**Cutover command sequence:**
- Dry run: `docker compose run --rm --no-deps app python scripts/renomear_codigo_tenant.py --old GPRB --new SCG33REAA`
- Apply after the dry-run check: `docker compose run --rm --no-deps app python scripts/renomear_codigo_tenant.py --old GPRB --new SCG33REAA --apply`
- If preconditions fail, do not apply; resume the existing app container with `docker compose start app`.
- After apply: `docker compose up -d app`, then `docker compose restart` for all active services.

**Files:**
- Use: `scripts/renomear_codigo_tenant.py` from the tenant-code plan
- Verify: `docker-compose.yml`, app and active service containers

**Interfaces:**
- The tenant rename CLI must support dry-run and require `--apply` for the database update.

- [ ] **Step 1: Run** `python manage.py check` and the focused tenant, route, authentication, and email test files; resolve failures introduced by this specification.
- [ ] **Step 2: Run** the full `python -m pytest -q` suite; record unrelated failures, including the existing `test_nova_atividade_requer_post` mismatch if it remains.
- [ ] **Step 3: Build** the application image with `docker compose build app` before touching the live tenant row.
- [ ] **Step 4: Stop** the app service, run the tenant rename CLI in dry-run mode and verify exactly one `GPRB` row and zero `SCG33REAA` rows.
- [ ] **Step 5: Apply** the guarded database rename with `--apply`; verify the same tenant ID now has code `SCG33REAA` and all other tenant/user counts are unchanged.
- [ ] **Step 6: Start the rebuilt app**, restart the other active Compose containers as requested, and verify `docker compose ps`, `/iniciacao/`, the `/recepcao/` alias, and `/static/img/logow.webp`.
