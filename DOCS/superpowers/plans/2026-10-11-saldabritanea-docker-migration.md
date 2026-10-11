# Docker `saldabritanea` Database Migration Implementation Plan

> **Execution status:** cutover completed and verified on 2026-10-11; migration-only changes staged for commit.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a new Docker PostgreSQL database named `saldabritanea` the CRM's only active Django database by restoring only the current Docker database `gprbr` into it.

**Architecture:** Create a new logical database inside the existing `gprbr-db` container, preserving `gprbr` as the source and rollback. Point Django to the Docker database, remove the app's connection settings for the separate external PostgreSQL instance that happens to have the same database name, and defer GPRB-dependent feature fixes.

**Tech Stack:** Docker Compose, PostgreSQL 15, Django 5.2, psycopg 3, pytest, PowerShell.

**Spec:** `DOCS/superpowers/specs/2026-10-11-saldabritanea-docker-database-migration-design.md`

## Global Constraints

- The destination is a **new logical database** named `saldabritanea` inside the existing Docker service `gprbr-db`.
- Migrate only the Docker database `gprbr`; do not import tables or data from the external PostgreSQL instance also named `saldabritanea`.
- Never overwrite an existing Docker database named `saldabritanea`; stop and inspect it first.
- Keep the source database `gprbr`, its volume, and the external same-name instance untouched.
- Do not run `docker compose down -v`, remove volumes, or modify `esfera-postgres`.
- Remove the app's external `GPRB_DB_*` connection configuration. GPRB-dependent feature issues are deferred, not fixed in this migration.
- Keep database dumps outside the repository and preserve unrelated workspace changes.
- The workspace already contains unrelated uncommitted changes; do not stage or commit them as part of this migration.

## Review Focus

- **`saldabritanea` already exists inside `gprbr-db`:** stop without overwriting; pin in the preflight step.
- **Dump is empty/corrupt or restore fails:** keep the app on `gprbr`; validate with `pg_restore --list` before creating the target.
- **Compose/environment still points Django at `gprbr`:** assert `current_database()` is `saldabritanea` after cutover.
- **External `GPRB_DB_HOST` leaks into the recreated app:** assert the app has no external GPRB connection variables and the connector stays in disabled/degraded mode.
- **Changing `POSTGRES_DB` is mistaken for creating a DB on an initialized volume:** explicitly create/restore the target and keep the existing volume mounted.

---

### Task 1: Configure the Docker target and prevent external GPRB connections

**Files:**
- Modify: `core/settings.py`
- Modify: `core/gprb/connection.py`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `.env` (ignored local config; change only `DB_NAME`, never print or stage credentials)
- Modify: `teste/conftest.py`
- Modify: `DOCS/README.md`
- Modify: `.specify/memory/constitution.md`
- Modify: `specs/legacy/database.md`
- Modify: `specs/legacy/architecture.md`
- Create: `teste/test_database_config.py`
- Create: `teste/test_gprb_external_disabled.py`

**Interfaces:**
- Produces: `settings.DATABASES['default']['NAME']` defaults to `saldabritanea`; explicit `DATABASE_URL` continues to take precedence.
- Produces: `settings.GPRB_DB_ENABLED = False`; `core.gprb.connection.connect()` returns `_DummyConnection` without opening a network connection when disabled.
- The app service in Compose points Django to the Docker service `db` and does not receive external `GPRB_DB_*` variables.

- [x] **Step 1: Write failing database target tests**

In `teste/test_database_config.py`, add `test_default_database_name_is_saldabritanea` with `DATABASE_URL`/`PGDATABASE` cleared, and `test_database_url_override_still_wins` with a safe test URL.

- [x] **Step 2: Write the failing external-connector guard test**

In `teste/test_gprb_external_disabled.py`, add `test_external_gprb_connection_is_disabled_by_default`; monkeypatch `psycopg.connect` and the socket probe to fail if called, then assert `connect()` returns `_DummyConnection`. Add `test_disabled_connector_does_not_reuse_cached_connection`; seed `_tls.conn` with a fake open connection and assert it is closed/cleared rather than reused.

- [x] **Step 3: Run the new tests and confirm they fail**

Run: `python -m pytest teste/test_database_config.py teste/test_gprb_external_disabled.py -q`
Expected: FAIL because the default DB name and disabled-connector setting are not implemented.

- [x] **Step 4: Implement the target defaults and connection guard**

Set the Django fallback database name to `saldabritanea` and preserve `DATABASE_URL` precedence. Define `GPRB_DB_ENABLED = False`; make `connect()` check this setting before reusing `_tls.conn` or entering `_nova_conexao()`. When disabled, close/clear any cached connection and return `_DummyConnection` without reading external credentials or opening a socket.

- [x] **Step 5: Point Compose defaults to the Docker target**

In `docker-compose.yml`, change the `DB_NAME` fallback used by `POSTGRES_DB`, the healthcheck, and `DATABASE_URL` to `saldabritanea`. Remove the app service's external `GPRB_DB_*` environment entries. Update `.env.example` database name/URL to match. The active ignored `.env` currently sets `DB_NAME=gprbr`; use a Python edit to change only that value, preserving every other line and never printing or staging credentials.

- [x] **Step 6: Keep GPRB test fixtures isolated**

Update `banco_gprb_teste` in `teste/conftest.py` to opt in only when explicit `GPRB_TEST_DB_HOST`, `GPRB_TEST_DB_PORT`, `GPRB_TEST_DB_USER`, and `GPRB_TEST_DB_PASSWORD` settings target an allowlisted local/Compose endpoint (`localhost`, `127.0.0.1`, `::1`, or `db`). Use only the database `saldabritanea_test`; skip if config, connection, or required schema is unavailable. Restore every overridden setting/environment variable after the fixture.

- [x] **Step 7: Update the approved architecture documents**

Change `DOCS/README.md`, `.specify/memory/constitution.md`, `specs/legacy/database.md`, and `specs/legacy/architecture.md` to identify the Docker `saldabritanea` instance as the one active Django database, distinguish it from the external instance with the same name, and record that GPRB-dependent UI fixes are deferred. Preserve unrelated pre-existing copy/branding edits in `DOCS/README.md`.

- [x] **Step 8: Run focused tests and Django checks**

Run: `python -m pytest teste/test_database_config.py teste/test_gprb_external_disabled.py -q` and `python manage.py check`
Expected: PASS; the default and explicit URL behavior are correct, and the disabled connector never calls psycopg.

- [x] **Step 9: Review the scoped diff without staging unrelated work**

Run `git diff --` for the tracked files in this task and confirm the changes are limited to the migration. Verify the effective `DB_NAME` without printing other `.env` values. Do not stage or commit these already-modified user files.

### Task 2: Back up `gprbr` and restore it into the new Docker database

**Files:**
- No source-file changes; operate only on `gprbr-db` after Task 1 passes.
- Backup: `C:\Users\mosan\AppData\Local\Temp\opencode\gprbr-to-docker-saldabritanea-<timestamp>.dump` (never add to Git).

**Interfaces:**
- Consumes: Compose target settings from Task 1.
- Produces: a new logical database `saldabritanea` in `gprbr-db`, restored only from `gprbr`.

- [x] **Step 1: Preflight container, source, destination, and volume**

Confirm `gprbr-db` is healthy, the expected Compose project/volume is mounted, `gprbr` exists, and `saldabritanea` does **not** exist inside this container. Verify the container's `POSTGRES_USER` is `gprbr` before using the commands below; if not, substitute the verified role. The external instance with the same name is not the target. If any check is uncertain or the Docker target exists, stop without changing the database.

- [x] **Step 2: Create a custom-format backup of `gprbr`**

Run the dump inside the container and copy it as a binary file to the approved temporary directory. Replace the timestamp placeholder with the current time; do not stream the archive through PowerShell text redirection.

```powershell
docker exec gprbr-db pg_dump -U gprbr -Fc -d gprbr -f /tmp/gprbr-to-saldabritanea.dump
docker cp gprbr-db:/tmp/gprbr-to-saldabritanea.dump "C:\Users\mosan\AppData\Local\Temp\opencode\gprbr-to-docker-saldabritanea-YYYYMMDD_HHMMSS.dump"
```

Expected: the host archive exists and has non-zero size.

- [x] **Step 3: Validate the archive before creating the target**

Run `docker exec gprbr-db pg_restore --list /tmp/gprbr-to-saldabritanea.dump` and confirm it lists the expected `gprbr` schema objects. On failure, stop; leave the source and app configuration unchanged.

- [x] **Step 4: Create and restore the new database**

Run these commands inside `gprbr-db`. Do not pass `--clean` and do not alter `gprbr`.

```powershell
docker exec gprbr-db createdb -U gprbr saldabritanea
docker exec gprbr-db pg_restore --exit-on-error --no-owner -U gprbr -d saldabritanea /tmp/gprbr-to-saldabritanea.dump
```

Expected: restore exits successfully; the new database has the source schema/data.

- [x] **Step 5: Compare source and destination**

Compare public table names and exact row counts between `gprbr` and the Docker `saldabritanea`. Expected: a complete copy of `gprbr`; no GPRB-only tables/data imported from the external instance. Stop and investigate any mismatch before cutover.

### Task 3: Cut over the Docker application without removing its volume

**Files:**
- No additional source-file changes; restart only Compose services after Task 2 validation.

**Interfaces:**
- Consumes: the restored Docker database `saldabritanea` from Task 2.
- Produces: the running app uses `saldabritanea`; the old Docker `gprbr` database remains available for rollback.

- [x] **Step 1: Apply the database service configuration with the same volume**

Run `docker compose up -d db` using the existing Compose project. Verify the existing named volume remains mounted and the database healthcheck is healthy; never run `down -v` or remove the volume.

- [x] **Step 2: Rebuild and restart only the application service**

Run `docker compose build app`, then `docker compose up -d --no-deps app`. The entrypoint may run Django migrations against the restored target; do not point it back to the external same-name instance.

- [x] **Step 3: Verify the live Django connection**

Query `current_database()` from the running app container. Expected: `saldabritanea`. Verify the Django connection host is the Compose service `db`.

- [x] **Step 4: Verify external GPRB settings are absent**

Inspect only environment variable **names** in `gprbr-app`; verify external `GPRB_DB_HOST`, `GPRB_DB_USER`, and `GPRB_DB_PASSWORD` are not present and `GPRB_DB_ENABLED` is false. Do not print secret values. GPRB-dependent screens may be degraded until the follow-up work.

### Task 4: Migration verification and handoff

**Files:**
- Test: `teste/test_database_config.py`, `teste/test_gprb_external_disabled.py`, and safe CRM regression tests.

- [x] **Step 1: Run migration-focused regression tests**

Run: `python -m pytest teste/test_database_config.py teste/test_gprb_external_disabled.py -q`
Expected: PASS for database selection and external-connector isolation. A post-cutover run including `teste/test_login_web.py` passed once; a later rerun hit duplicate fixture data in pytest's reused test database. Do not drop/reset that database in this migration. Separately rerun the known baseline `teste/test_fase_a_funil.py` failures and record them; do not fix them here.

- [x] **Step 2: Run container health and Django system checks**

Run: `docker exec gprbr-app python manage.py check` and inspect `/healthz/`. Expected: HTTP 200 and no Django system-check errors.

- [x] **Step 3: Confirm preservation and report**

Confirm `gprbr` and its Docker volume still exist, the external same-name database was not targeted, the backup remains outside Git, and the active Django connection is `saldabritanea`. Report the backup path and any deferred GPRB feature failures; do not delete either source database.

## Execution record

- Live app uses Docker `saldabritanea` on Compose host `db`; both app and database containers are healthy. The source `gprbr` remains present on the same named volume.
- Source and target each contain 37 public tables with identical table names and exact row counts. The 135,063-byte dump is outside Git and readable by `pg_restore --list`.
- Migration-only regression command passed: `python -m pytest teste/test_database_config.py teste/test_gprb_external_disabled.py -q` (8 passed). Django checks passed on host and container; `/healthz/` returned 200; no Django migrations are pending.
- A later combined migration/login run reached 21 passes but ended with 2 login-test setup/teardown errors (duplicate fixture user and a deadlock in the reused `test_saldabritanea` database). The test database was not reset or dropped.
- Deferred baseline: `python -m pytest teste/test_fase_a_funil.py -q` produced 9 failures and 7 passes, matching the previously recorded unrelated CRM failures.
- Full suite `python -m pytest teste/ -q` exceeded the 600-second limit around 45% and had already emitted failures; it is not reported as passing. The remaining suite problems are deferred per the user's direction.
- Scope ruling: stage only migration-specific hunks/files. Preserve the broader in-progress `DOCS/README.md` rewrite and unrelated workspace changes; stage a minimal migration note instead.
