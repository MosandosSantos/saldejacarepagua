# Spec: 004 — Problema Relatório

**Criada**: 2026-10-02 · **Fonte**: `specs/legacy/code-audit-2026-10-02.md` · **Status**: Draft

## Objetivo

Reduzir a dívida do domínio de relatórios/dashboard: eliminar código morto, domar as funções de alta complexidade e unificar exportações, sem alterar comportamento visível ao usuário.

## Problemas com evidência

| # | Problema | Evidência | Severidade |
|---|----------|-----------|------------|
| R1 | **App inteiro morto**: `export_dashboard/` (526 linhas em views) — ninguém importa | grep de imports negativo | Média (ruído/manutenção) |
| R2 | **Módulo morto**: `core/gprb_read.py` — ninguém importa | grep de imports negativo | Média |
| R3 | `ranking_dados` rank **E (33)** — monta meetings, members, attendances e stats em uma função | radon `core/gprb/ranking.py:126` | Alta |
| R4 | `exportar_csv` duplicado em 2 views | grep `def exportar_csv` ×2 | Média |
| R5 | Dashboard faz **12 queries GPRB por render** (mitigado por cache, mas agregável) | `dashboard/views.py` — 12 chamadas `repo.` | Média |

## Requisitos

- **RF-01**: `export_dashboard/` e `core/gprb_read.py` removidos do repositório (após confirmação de zero imports em CI/grep).
- **RF-02**: `ranking_dados` decomposto em funções coesas por responsabilidade (busca de meetings, join de presenças, cálculo de stats), cada uma com rank ≤ C.
- **RF-03**: Um único utilitário de exportação CSV reutilizado por todas as views que exportam.
- **RF-04**: Comportamento externo preservado: mesmas colunas, mesmos filtros, mesmos valores nas telas e exports (regressão por comparação).

## Critérios de aceite

- `grep -rn "export_dashboard\|gprb_read"` retorna zero ocorrências fora de specs/docs.
- `radon cc core/gprb/ranking.py -s -n D` vazio.
- Dashboard e relatórios renderizam 200 com dados de exemplo; CSV exportado idêntico ao anterior (diff).

## Fora de escopo

- Novos relatórios; mudança visual; persistência de KPIs (ex-`kpi_snapshot`).
