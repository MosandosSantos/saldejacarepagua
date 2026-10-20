# Tasks: 003 — Problema Estoque

- [ ] **T1. Registrar decisão de produto (tem ou não estoque?)**
  - Acceptance: decisão com data/responsável anotada nesta spec (seção Requisitos RD-01).
  - Verify: arquivo atualizado + `known-problems.md` reflete o estado.
  - Files: `specs/003-problema-estoque/spec.md`, `specs/legacy/known-problems.md`.

- [ ] **T2. (Condicional) Se estoque for necessário: abrir spec completa**
  - Acceptance: `specs/00N-estoque-<nome>/spec.md` criada via `/speckit.specify` com requisitos próprios.
  - Verify: feature.json aponta para a nova feature quando o fluxo iniciar.
  - Files: `specs/<novo>/`, `.specify/feature.json`.

> Nenhuma task de código nesta spec hoje — o domínio está limpo (zero remanescentes).
