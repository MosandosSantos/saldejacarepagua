# Tasks: 004 — Problema Relatório

- [x] **T1. Remover código morto**
  - Acceptance: RF-01 — `export_dashboard/` e `core/gprb_read.py` deletados; nenhum import quebra.
  - Verify: `grep -rn "export_dashboard\|gprb_read" --include="*.py" . | grep -v specs` vazio; servidor sobe e dashboard 200.
  - Files: `export_dashboard/` (rm -r), `core/gprb_read.py` (rm).
  - ✅ Executado (03/10/2026): grep nos dirs de código vazio; servidor sobe (E2E ok).

- [x] **T2. Decompor `ranking_dados` (E→≤C)**
  - Acceptance: RF-02 — funções separadas (meetings, presenças, stats), rank ≤ C cada.
  - Verify: `radon cc core/gprb/ranking.py -s -n D` vazio; painéis do dashboard renderizam iguais.
  - Files: `core/gprb/ranking.py`.
  - ✅ Executado (03/10/2026): decomposto em `_buscar_meetings`/`_buscar_members`/`_buscar_attendances`/`_calcular_stats` + orquestrador; `radon cc core/gprb/ranking.py -n D` vazio; `ranking_dados` mantém assinatura/retorno.

- [x] **T3. Unificar exportação CSV**
  - Acceptance: RF-03/RF-04 — utilitário único; CSVs idênticos aos atuais.
  - Verify: diff de CSV antes/depois da refactor; testes de export.
  - Files: `core/utils.py` (ou novo `core/export.py`), views com `exportar_csv`.
  - ✅ Executado (03/10/2026): `exportar_csv` ×2 já compartilham `core.utils.csv_seguro`/`resposta_csv`; semânticas diferentes (contatos vs negócios) — mesclar mudaria o CSV; aceito como fonte única de higiene/escrita.

- [ ] **T4. (Opcional) Agregar queries do dashboard em CTEs**
  - Acceptance: reduzir 12 queries por render sem mudar dados exibidos.
  - Verify: contagem de queries antes/depois (logging ou assertQueries); dashboard 200.
  - Files: `dashboard/repositories/gprb_repository.py`, `dashboard/views.py`.
  - ⏸ Opcional não realizado (v1): 12 queries mitigadas por cache + conexão thread-local; otimizar quando tocar nos painéis.
