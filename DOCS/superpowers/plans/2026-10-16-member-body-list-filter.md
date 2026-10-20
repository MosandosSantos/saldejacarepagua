# Member Body List Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` for native execution. Follow the steps in order; each has its own test cycle.

**Goal:** Filter the Membro list by the Corpo of linked Lojas, while preserving tenant isolation and all existing list filters.

**Architecture:** The member GET view reads repeated `corpo` values and filters its tenant-scoped queryset through `Membro.lojas__corpo`. A member matches if any same-tenant linked Loja matches any selected body; `.distinct()` prevents M2M duplicates. Body and existing filters combine by AND, while multiple body values combine by OR. The existing GET form submits the selected bodies immediately and preserves its other parameters.

**Tech Stack:** Django 5.2, Python 3.13, PostgreSQL, Django templates, Tailwind, pytest-django.

**Spec:** `specs/008-filtros-corpo-listas/SPEC-member-body-list-filter.md`

## Global Constraints

- Use the five stored values `perfeicao`, `capitulo`, `kadosh`, `consistorio`, and `sc33` from `Loja.CORPO_CHOICES`.
- Filter Membros by linked Loja bodies, not by `GrauMembro` history.
- Require the related Loja to have the same `tenant_id` as the Membro.
- Multiple bodies combine by OR; each body criterion combines by AND with `q`, situation, Vale, selected Loja, UF, city, and annuity filters.
- When a specific Loja is selected together with a body, both constraints must match the same Loja relation.
- No body selected means no body predicate; unknown body values return no results.
- Preserve current tenant scope, permissions, pagination/ordering, and no duplicate Membro rows.
- Do not add schema changes or runtime dependencies.

## Review Focus

- A member linked only to another tenant's matching Loja must not appear — test in Task 1.
- A member linked to multiple bodies appears once when multiple body values are selected — test in Task 1.
- A selected Loja and body must match the same linked Loja, not two different Lojas — test in Task 1.
- A body filter combined with `q` or other existing filters must narrow, not replace, them — test in Task 1.
- No body selected must preserve the current rows and selected search/filter values — tests in Tasks 1–2.

---

## File Structure

- `contatos/views/crud.py`: parse/validate repeated body values and combine them with the tenant-scoped member queryset and existing M2M filters. The `/contatos/` route re-exports `views.lista` from this module.
- `contatos/templates/contatos/lista.html`: render the five body checkboxes in the existing GET filter form and submit immediately on change.
- `teste/test_membro_local.py`: cover body/source semantics, same-tenant joins, combined filters, duplicates, invalid values, and rendered selection state.

### Task 1: Filter members through same-tenant linked Loja bodies

**Files:**
- Modify: `contatos/views/crud.py`
- Test: `teste/test_membro_local.py`

**Interfaces:**
- Consumes: `Loja.CORPO_CHOICES` and the current tenant-scoped `Membro` queryset.
- Produces: view context `corpos_filtro`, a list of `{valor, rotulo, selecionado}`; parses repeated GET key `corpo`.
- Query contract: same-tenant related Loja with `corpo__in=selected_values`, combined in the same relation condition as `loja_id` when both filters are selected; apply `.distinct()`.

- [x] **Step 1: Write failing queryset tests**
  - `test_membro_lista_corpo_filtra_pelas_lojas_vinculadas`: matching member appears, member with only a different body does not, and member without a Loja is omitted when filtered.
  - `test_membro_lista_corpo_multiplos_valores_or_sem_duplicar`: member linked to two selected bodies appears once.
  - `test_membro_lista_corpo_exige_mesma_loja_se_loja_especifica`: member linked to a selected Loja and a different-body Loja is excluded when the selected body does not match the selected Loja.
  - `test_membro_lista_corpo_ignora_loja_de_outro_tenant`: a cross-tenant Loja relation cannot satisfy the member's body filter.
  - `test_membro_lista_corpo_combina_com_q_e_outros_filtros`: body selection narrows existing search/Loja filters by AND.
  - `test_membro_lista_corpo_invalido_nao_amplia_resultados` and `test_membro_lista_corpo_vazio_mantem_filtros_atuais`.
- [x] **Step 2: Run tests to verify RED**
  - Run: `.venv\Scripts\python.exe -m pytest --ds=core.settings_vale_test teste/test_membro_local.py -k corpo -q` with `VALE_TEST_DATABASE_URL` pointing at port 5434.
  - Expected: current view ignores body values and/or the cross-tenant/same-Loja cases return the wrong rows.
- [x] **Step 3: Implement the allowlisted same-tenant filter in `contatos/views/crud.py`'s `lista` view**
  - Validate every submitted value against `dict(Loja.CORPO_CHOICES)`; on an unknown value set the queryset to `.none()`.
  - With selected bodies, filter the M2M relation by selected `corpo` and `lojas__tenant_id == Membro.tenant_id`, then call `.distinct()`.
  - If `loja_id` is also present, combine it with the body predicate in the same relation filter so both apply to the same Loja.
  - Include body selection in `filtros_ativos`; preserve all other existing filters.
- [x] **Step 4: Run tests to verify GREEN**
  - `teste/test_membro_local.py -k corpo` → 7 passed, 9 deselected.

### Task 2: Add immediate Corpo checkboxes to the Membro list

**Files:**
- Modify: `contatos/templates/contatos/lista.html`
- Test: `teste/test_membro_local.py`

**Interfaces:**
- Consumes: `corpos_filtro` from Task 1.
- Produces: five native labeled checkbox inputs named `corpo` within the existing GET form; body changes submit immediately and preserve every other filter value.

- [x] **Step 1: Write failing rendered-form test**
  - `test_membro_lista_exibe_corpos_e_preserva_filtros`: all five values render, selected bodies remain checked, and `q`, Vale, Loja, situation and other active filters stay in the same form.
  - Assert no body “Todos” option is rendered.
- [x] **Step 2: Run the test to verify RED**
  - Run: `.venv\Scripts\python.exe -m pytest --ds=core.settings_vale_test teste/test_membro_local.py::test_membro_lista_exibe_corpos_e_preserva_filtros -q` with the test DB on port 5434.
  - Expected: body controls are absent.
- [x] **Step 3: Implement the accessible responsive controls**
  - Add the checkbox fieldset to the existing GET form; submit on body change, keeping all selected values. Keep the existing Limpar link semantics.
- [x] **Step 4: Verify form and browser behavior**
  - Run the form test; in a browser fixture toggle two bodies and confirm immediate GET serialization retains `q`, Vale and Loja values and both body values.
  - Browser fixture confirmed the GET payload retained `q=Ana`, `loja=13`, `situacao=ATIVO`, and all selected bodies through repeated submissions.

### Task 3: Integrated verification

- [x] Run the focused `teste/test_membro_local.py` suite: 17 passed.
- [x] Run the combined Loja/Membro/Acompanhamento focused regression after both list filters: `113 passed, 7 deselected`.
- [x] Run Django/migration checks and targeted Ruff; checks passed with existing `I001,E741` findings in `crud.py` ignored.
- [x] Run the layout detector on `contatos/templates/contatos/lista.html`; no findings.
- [x] Rebuild the local app; container healthy and `/healthz/` returned HTTP 200.
