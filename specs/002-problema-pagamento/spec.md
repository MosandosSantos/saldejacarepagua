# Spec: 002 — Problema Pagamento (integridade de escritas GPRB)

**Criada**: 2026-10-02 · **Fonte**: `specs/legacy/code-audit-2026-10-02.md` · **Status**: Draft

## Objetivo

Garantir atomicidade e padrão seguro nas escritas do modelo GPRB — **pré-requisito bloqueante para o módulo Financeiro** (`specs/001-financeiro-anuidades`), que fará escritas financeiras multi-tabela.

## Problemas com evidência

| # | Problema | Evidência | Severidade |
|---|----------|-----------|------------|
| P1 | **Escritas multi-statement não atômicas**: conexão com `autocommit=True` torna cada `execute()` permanente; o `commit()` final é no-op | `core/gprb/connection.py` (`autocommit=True`) + `definir_lojas_membro` (DELETE→INSERTs→UPDATE sem transação real) | **Crítica — risco de perda de vínculos membro↔lojas** |
| P2 | SQL montado por f-string/concatenação (padrão frágil) em 7 pontos | Bandit B608: `core/gprb/members.py:25,55`, `core/gprb/ranking.py:99,223`, `dashboard/repositories/gprb_repository.py:98`, `repositories/gprb_repository.py:295,369` | Média |
| P3 | Escritas sem teste de rollback/falha | Ausência de testes na camada GPRB (`tests.md`, lacuna nº 1) | Alta |

## Requisitos

- **RF-01**: Toda escrita multi-statement GPRB deve rodar dentro de **transação explícita** (BEGIN → ... → COMMIT; ROLLBACK em erro) — incluindo `definir_lojas_membro`, `criar_prefeitura`, `atualizar_prefeitura`, `atualizar_loja` e as futuras escritas de pagamento.
- **RF-02**: Falha em qualquer statement da transação deve deixar o banco **no estado anterior** (nenhum efeito parcial visível).
- **RF-03**: Queries montadas dinamicamente devem separar **estrutura** (identificadores validados contra allowlist) de **valores** (sempre parametrizados).
- **RF-04**: Bandit não deve reportar B608 novo; os 7 existentes ou são corrigidos ou justificados com `# nosec` + comentário do allowlist aplicado.

## Critérios de aceite

- Teste de falha proposital no meio de `definir_lojas_membro` (ex.: INSERT de loja inexistente) → `member_loja` permanece **intacta** (rollback comprovado).
- `bandit -r repositories/ core/gprb/ dashboard/repositories/` sem B608 não-justificado.
- Fluxo E2E de edição de membro com 2+ lojas continua funcionando (regressão).

## Fora de escopo

- Implementação do módulo Financeiro em si (spec própria já aprovada: `specs/001-financeiro-anuidades`); migrations de schema; índices adicionais.
