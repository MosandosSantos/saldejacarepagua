# Iniciação Route and Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Use `superpowers:subagent-driven-development` only if the user explicitly chooses that approach.

**Goal:** Make `/iniciacao/` the canonical route for the existing reception flow while preserving `/recepcao/` URLs as compatible aliases.

**Architecture:** Mount the existing `recepcao` URL configuration at `/iniciacao/` under the existing `recepcao` namespace so reverse lookups produce the new path. Mount the same handlers at `/recepcao/` under a unique legacy namespace, and update application-generated links and AJAX requests to the canonical prefix.

**Tech Stack:** Django URL resolver, Django templates, JavaScript, pytest.

**Spec:** `DOCS/superpowers/specs/2026-10-10-amorio-tenant-navigation-brand-design.md`

## Global Constraints

- `/iniciacao/` is canonical for the root page and all subroutes.
- `/recepcao/` and all existing subroutes remain functional aliases, including POST handlers.
- Keep Python namespace `recepcao` and route names unchanged.
- Menu label is `Iniciação`; page heading is `Flow de Iniciação`.

## Review Focus

- Reverse lookup for `recepcao:kanban` returns `/iniciacao/`; pin in `teste/test_iniciacao_routes.py`.
- Legacy GET route still renders the same handler; pin in `teste/test_iniciacao_routes.py`.
- Legacy POST route preserves its method and reaches the same handler; pin with the existing `teste/test_kanban_views.py` fixture.
- AJAX calls generated from the new page use `/iniciacao/`; pin by asserting the rendered URL configuration or exercising the rendered endpoint.
- Unrelated `recepcao` route names remain stable; pin with reverse assertions for `novo_lead`, `mover`, and `excluir_negocio`.

---

### Task 1: Add canonical and legacy URL mounts

**Test cases:** `test_reverse_kanban_uses_iniciacao`,
`test_old_and_new_root_paths_reach_kanban`, and
`test_legacy_mover_path_preserves_post`.

**Files:**
- Modify: `core/urls.py`
- Create: `teste/test_iniciacao_routes.py`

**Interfaces:**
- Canonical namespace `recepcao` resolves to `/iniciacao/`.
- Legacy namespace `recepcao_legacy` resolves to `/recepcao/` and the same view functions.

- [ ] **Step 1: Write failing tests** asserting `reverse('recepcao:kanban') == '/iniciacao/'`, canonical and legacy GETs reach the existing handler, and the legacy POST route reaches `mover` without method conversion.
- [ ] **Step 2: Run** `python -m pytest teste/test_iniciacao_routes.py -q`; expect the canonical reverse and paths to fail.
- [ ] **Step 3: Mount** `recepcao.urls` under `iniciacao/` with namespace `recepcao` and under `recepcao/` with namespace `recepcao_legacy`; keep the URLconf and named routes unchanged.
- [ ] **Step 4: Run** `python -m pytest teste/test_iniciacao_routes.py teste/test_kanban_views.py -q`; expect both canonical and compatibility tests to pass.

### Task 2: Update navigation, page heading, and generated requests

**Test cases:**
- `test_reverse_kanban_uses_iniciacao`
- `test_old_and_new_root_paths_reach_kanban`
- `test_legacy_mover_path_preserves_post`
- `test_kanban_shows_iniciacao_branding`
- `test_kanban_ajax_urls_use_iniciacao_prefix`

**Files:**
- Modify: `acesso/context_processors.py`
- Modify: `recepcao/templates/recepcao/kanban.html`
- Modify: `locust/locustfile.py`
- Modify: `locust/README.md`
- Modify: `DOCS/README.md`
- Modify: `DOCS/PRD.md`
- Test: `teste/test_iniciacao_routes.py`

**Interfaces:**
- Navigation points to `reverse('recepcao:kanban')` and labels the item `Iniciação`.
- All generated fetch/form links for kanban movement and deletion use the canonical path.

- [ ] **Step 1: Add a failing rendered-page assertion** for the `Iniciação` nav link, the `Flow de Iniciação` heading, and canonical AJAX prefixes.
- [ ] **Step 2: Run** `python -m pytest teste/test_iniciacao_routes.py -q`; expect the old label, heading, or request prefix to fail.
- [ ] **Step 3: Update** the navigation label, heading, three kanban AJAX prefixes, load-test target, and route documentation. Leave existing tests that request `/recepcao/` in place as compatibility coverage.
- [ ] **Step 4: Run** `python -m pytest teste/test_iniciacao_routes.py teste/test_kanban_views.py teste/test_viewer.py -q`; expect the focused navigation and route tests to pass.
