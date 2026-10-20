# Spec: 003 — Problema Estoque

**Criada**: 2026-10-02 · **Fonte**: `specs/legacy/code-audit-2026-10-02.md` · **Status**: Draft (decisão de produto pendente)

## Objetivo

Documentar o estado do domínio de estoque e resolver a pendência de decisão: **o módulo não existe mais** e não há remanescentes a limpar — resta decidir se a organização precisa de um.

## Problemas com evidência

| # | Problema | Evidência | Severidade |
|---|----------|-----------|------------|
| E1 | Módulo de estoque **removido por decisão** na migração do banco (tabelas `inventory_item` e `inventory_movement` descartadas por falta de uso real) | `DOCS/README.md` (lista de excluídos) + grep: **zero referências** a inventory no código ativo | Info |
| E2 | Expectativa do usuário de que "estoque" é uma área do sistema | Pedido original de migração ("não vai ter a tabela classe e nem inventory e afins") vs. demanda atual por spec de problema | Info |

## Verificação realizada

- `grep -rn "inventory" --include="*.py"` em todo o código ativo: **nenhuma ocorrência**.
- Nenhuma view, rota, template ou model remete a estoque.
- Banco `saldabritanea`: sem tabelas de estoque (correto conforme decisão).
- Backups: dados antigos de inventário preservados em `backups/saldogprb_backup_20261002.dump` (recuperáveis se necessário).

## Requisitos (de decisão, não de código)

- **RD-01**: Dono do produto confirma se há necessidade real de controle de estoque no CRM (ex.: itens de loja, livros, insígnias).
  - Se **não**: marcar esta spec como "fechada por decisão" e remover de backlog.
  - Se **sim**: nova spec completa via `/speckit.specify` (modelo, telas, permissões) — **não** reutilizar as tabelas antigas.

## Critérios de aceite

- Esta spec contém a decisão registrada com data e responsável.
- `known-problems.md` reflete o estado final do domínio.

## Fora de escopo

- Qualquer implementação de estoque nesta spec; recuperação de dados antigos.
