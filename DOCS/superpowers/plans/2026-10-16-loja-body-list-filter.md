# Loja Body List Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` for native execution. Follow the steps in order; each has its own test cycle.

**Goal:** Let users filter the Loja list by the five stored body categories while preserving search, tenant scope, and immediate checkbox filtering.

**Architecture:** The GET view reads repeated `corpo` values, validates them against `Loja.CORPO_CHOICES`, and applies `corpo__in` to the existing tenant-scoped queryset. The Loja search and body controls share one GET form; toggling a body submits immediately, selected bodies combine by OR, and no selected body adds no category predicate.

**Tech Stack:** Django 5.2, Python 3.13, PostgreSQL, Django templates, Tailwind, pytest-django.

**Spec:** `specs/008-filtros-corpo-listas/SPEC-loja-body-list-filter.md`

## Global Constraints

- Use the stored values `perfeicao`, `capitulo`, `kadosh`, `consistorio`, and `sc33` from `Loja.CORPO_CHOICES`.
- No body checkbox selected means no body filter; do not add a “Todos” checkbox.
- Multiple selected bodies combine by OR; the existing text query `q` combines by AND.
- Preserve `_lojas_visiveis` tenant scoping, existing search fields, sort order, and actions.
- Unknown body IDs must not broaden the queryset; return no results.
- Do not add a migration or runtime dependency.
- Use the existing CRM test database via `core.settings_vale_test` at `127.0.0.1:5434`.

## Review Focus

- An unknown `corpo` must not fall back to an unfiltered list — test in Task 1.
- `q` plus a selected body must be ANDed, not accidentally overwritten — test in Task 1.
- Multiple bodies must not duplicate a Loja — test in Task 1.
- No selected body must preserve all rows allowed by tenant and `q` — test in Task 1.
- Changing a checkbox must preserve the search term and checked body state through GET navigation — test in Task 2/browser fixture.

---

## File Structure

- `contatos/views/gprb_lojas.py`: validate repeated `corpo` parameters, apply the body predicate to the existing list queryset, and supply checkbox state.
- `contatos/templates/contatos/lojas.html`: keep search and body controls in the same GET form; render accessible body checkboxes with immediate submit.
- `teste/test_loja_local.py`: cover filtering, combinations, invalid values, selected state and tenant scope.

### Task 1: Filter the tenant-scoped Loja queryset by body

**Files:**
- Modify: `contatos/views/gprb_lojas.py`
- Test: `teste/test_loja_local.py`

**Interfaces:**
- Consumes: `Loja.CORPO_CHOICES` and the existing `_lojas_visiveis(request)` queryset.
- Produces: view context `corpos_filtro`, a list of `{valor, rotulo, selecionado}` options using the model's fixed choices.
- Query contract: repeated GET parameter `corpo`; body predicate `corpo__in=selected_values`; text search and body predicate compose with AND.

- [x] **Step 1: Write failing queryset tests**
  - `test_loja_lista_corpo_filtra_pelo_selecionado`: matching body visible, other body absent.
  - `test_loja_lista_corpo_multiplos_valores_combinam_por_or_sem_duplicar`: two categories return both groups exactly once.
  - `test_loja_lista_corpo_combina_com_busca_por_and`: query text narrows the selected body results.
  - `test_loja_lista_corpo_desconhecido_nao_amplia_resultados`: unknown value returns no rows.
  - `test_loja_lista_corpo_vazio_mantem_todas_as_lojas`: no category leaves the current result set intact.
- [x] **Step 2: Run tests to verify RED**
  - Run: `.venv\Scripts\python.exe -m pytest --ds=core.settings_vale_test teste/test_loja_local.py -k loja_lista_corpo -q` with `VALE_TEST_DATABASE_URL` pointing at the test database on port 5434.
  - Expected: body query parameters are ignored and/or checkbox context is absent; failures identify the missing predicate.
- [x] **Step 3: Implement the allowlisted query filter**
  - Parse `request.GET.getlist('corpo')`; if any value is outside `dict(Loja.CORPO_CHOICES)`, set `qs = qs.none()`; otherwise filter with `corpo__in` when selected values exist.
  - Keep the filter after `_lojas_visiveis` and compose it with existing `q` using queryset AND semantics.
  - Populate `corpos_filtro` with all five values and selected state.
- [x] **Step 4: Run tests to verify GREEN**
  - Run the same `-k loja_lista_corpo` command; `5 passed, 15 deselected`, with no duplicate rows.

### Task 2: Add immediate body checkboxes to the Loja list

**Files:**
- Modify: `contatos/templates/contatos/lojas.html`
- Test: `teste/test_loja_local.py`

**Interfaces:**
- Consumes: `corpos_filtro` from Task 1.
- Produces: one GET form containing the current `q` search input and repeated `corpo` checkbox inputs; changing a checkbox calls `form.requestSubmit()`.

- [x] **Step 1: Write failing form tests**
  - `test_loja_lista_exibe_corpos_e_preserva_selecao`: all five choices render; selected checkbox and `q` remain populated after GET.
  - Assert there is no “Todos” body checkbox and the search input and body controls belong to the same form.
- [x] **Step 2: Run tests to verify RED**
  - Run: `.venv\Scripts\python.exe -m pytest --ds=core.settings_vale_test teste/test_loja_local.py::test_loja_lista_exibe_corpos_e_preserva_selecao -q` with the test DB on port 5434.
  - Expected: body controls are absent and search/body are not submitted together.
- [x] **Step 3: Implement the responsive controls**
  - Move the existing search input and body checkboxes into a shared GET form. Reuse HAZON colors/radii and native labeled checkboxes. Submit on checkbox change; preserve `q` and all selected `corpo` values. Unchecking the last body returns to the full list (still respecting `q`).
- [x] **Step 4: Verify the interaction**
  - Run the form test and use a browser fixture with a search term plus two bodies: changing the body submits immediately, preserves `q`, and serializes both checked bodies.
  - `test_loja_lista_exibe_corpos_e_preserva_selecao` passed; Chrome fixture recorded immediate GET submissions with `q=Estrela`, OR selections, and unchecking back to only `q`.

### Task 3: Integrated checks

- [x] Run `teste/test_loja_local.py` excluding only the two documented baseline failures; `19 passed, 2 deselected`.
- [x] Run Django/migration checks and targeted Ruff with documented legacy-rule ignores; checks passed.
- [x] Run the layout detector on `contatos/templates/contatos/lojas.html`; no findings.
- [x] Rebuild the local app; container healthy and `/healthz/` returned HTTP 200.
