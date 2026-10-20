# Spec: 005 — Problema Permissões

**Criada**: 2026-10-02 · **Fonte**: `specs/legacy/code-audit-2026-10-02.md` · **Status**: Draft

## Objetivo

Centralizar e testar o controle de permissões do painel web (RBAC), eliminando a função mais complexa do código e cobrindo com testes o lado web — hoje só a API tem RBAC testado.

## Problemas com evidência

| # | Problema | Evidência | Severidade |
|---|----------|-----------|------------|
| PM1 | `_montar_contexto` rank **F (45)** — todos os caminhos de permissão/tenant/config em uma função | radon `acesso/views/config.py:354` | **Crítica** |
| PM2 | `_processar_etapa` rank D (25) e `equipe` rank D (28) no mesmo domínio | radon `acesso/views/config.py:243`, `acesso/views/equipe.py:45` | Alta |
| PM3 | **RBAC web sem testes**: `viewer` bloqueado na API (`test_rbac_api.py`, `test_viewer.py`) mas sem teste nas views web (contatos, potências, lojas, financeiro, equipe, config) | Ausência de testes com `web_login_required`/`web_requer_edicao` | Alta |
| PM4 | Escopo de permissões espalhado (`qs_escopo` + decorators + checks inline duplicados) | greps de `Usuario.objects.filter` + `qs_escopo` em múltiplos módulos | Média |

## Requisitos

- **RF-01**: `_montar_contexto` decomposta em funções por seção (perfil, equipe, tenant, preferências), cada uma rank ≤ C; comportamento da página `/config/` inalterado.
- **RF-02**: Matriz de permissões web testada: para cada papel (`admin_saas`, `admin_company`, `operacional`, `viewer`) e cada rota de escrita (POST em membros, potências, lojas, financeiro, equipe, config) — viewer bloqueado (403/redirect), operacional liberado onde previsto, admin liberado.
- **RF-03**: Utilitário único de escopo de tenant/papel (`qs_escopo` consolidado) usado por todas as listagens; duplicações removidas.
- **RF-04**: Nenhuma rota de escrita sem decorator de autenticação + permissão (varredura de `urlpatterns` × views).

## Critérios de aceite

- `radon cc acesso/views/config.py -s -n D` vazio.
- Nova suíte `teste/test_rbac_web.py` verde cobrindo a matriz RF-02.
- `grep` de rotas de escrita sem decorator retorna vazio (script de varredura simples documentado na task).

## Fora de escopo

- Novos papéis (ex.: tesoureiro); alteração da matriz da API; permissões por registro (row-level).
