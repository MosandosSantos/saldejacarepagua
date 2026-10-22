# Auditoria de código — 02/10/2026

> Levantamento estático + manual do código ativo (sem `_legacy/`, venvs, migrations).
> Ferramentas: **radon** (complexidade/LOC), **bandit** (segurança, JSON em `logs/bandit.json`), greps manuais (SQL, segredos, duplicação, código morto).
> Destino das correções: specs numeradas `specs/001..005-problema-*` (spec.md + tasks.md cada).

## Resumo executivo

| Área | Achados |
|------|---------|
| Complexidade | **1 função rank F**, **3 rank E**, 11 rank D, **42 rank C**; 1 arquivo com BOM que quebra parser |
| Segurança | **0 HIGH**, 9 MEDIUM (7× SQL assembly, 1× mark_safe, 1× bind 0.0.0.0), 65 LOW; **sem segredos hardcoded** ✅ |
| SQL | **Escritas multi-statement não atômicas** (`autocommit=True` — risco de perda de vínculo membro↔lojas); SQL duplicado em 3 camadas; `coluna_existe` a cada request |
| Arquitetura | 2 cópias mortas inteiras (`export_dashboard/` 526 linhas, `core/gprb_read.py`); utilitários duplicados (`_txt`, `_sem_acento`, `_rodape`, `backfill_tenant_id`) |
| Performance | 12 queries GPRB por render do dashboard (cache mitiga); paginação OK na lista de membros (25/pág) ✅ |
| Tabelas removidas | `password_invite_token`, `auth_attempt`, `refresh_token`, `service_token`, `kpi_snapshot` — **zero referências no código** ✅ |

## 1. Complexidade ciclomática (radon)

### Rank F (crítico)
- `acesso/views/config.py:354 _montar_contexto` — **F (45)**: montagem de contexto de configuração com todos os caminhos de permissão/tenant em uma função.

### Rank E (muito grave)
- `repositories/gprb_repository.py:60 buscar_membro` — **E (35)**: montagem de SQL + filtros + montagem de dict em uma função.
- `core/gprb/ranking.py:126 ranking_dados` — **E (33)**: ranking completo (meetings, members, attendances, stats) em uma função.

### Rank D (grave) — 11 funções
| Local | Função | Score |
|-------|--------|-------|
| acesso/views/config.py:243 | `_processar_etapa` | D (25) |
| acesso/views/equipe.py:45 | `equipe` | D (28) |
| contatos/importador.py:225 | `importar_linhas` | D (26) |
| contatos/orcamento.py:100 | `gerar_orcamento_pdf` | D (21) |
| contatos/management/commands/seed_dados.py:347 | `_seed_contatos` | D (26) |
| contatos/views/captura.py:16 | `captura_lead` | D (26) |
| contatos/views/importacao.py:33 | `importar` | D (21) |
| automacoes/views.py:105 | `_parametros_do_passo` | D (23) |
| candidatos/views/crud.py:180 | `candidato_modal_detalhe` | D (22) |
| discador/views.py:238 | `fila_form` | D (22) |
| repositories/gprb_repository.py:409+ | `buscar_loja`, `listar_lojas`, `buscar_loja_para_edicao`, `atualizar_loja` | C (13–16) |

### Rank C — 42 funções
Distribuídas principalmente em `repositories/gprb_repository.py`, `dashboard/views.py`, `tarefas/views.py`, `gestao/views.py`, `acesso/views/*`.

### Arquivos gigantes (LOC)
| Arquivo | Linhas | Nota |
|---------|--------|------|
| `repositories/gprb_repository.py` | 779 | God-repo — dividir por domínio (membros/lojas/prefeituras/pagamentos) |
| `dashboard/views.py` | 702 | Mistura funil CRM + dashboards GPRB |
| `tarefas/views.py` | 677 | + BOM (abaixo) |
| `acesso/views/config.py` | 616 | Contém a única rank F |
| `export_dashboard/dashboard/views.py` | 526 | **Cópia morta** (ninguém importa) |
| `automacoes/views.py` | 424 | |
| `candidatos/oficialato.py` | 412 | |

### BOM inválido
- `tarefas/views.py` começa com **U+FEFF** — quebra parsers (radon: `ERROR: invalid non-printable character U+FEFF`). Python roda, ferramentas não.

## 2. Segurança (bandit: 0 HIGH, 9 MEDIUM, 65 LOW)

### MEDIUM
| ID | Local | Situação |
|----|-------|----------|
| B608 ×7 | `core/gprb/members.py:25,55` · `core/gprb/ranking.py:99,223` · `dashboard/repositories/gprb_repository.py:98` · `repositories/gprb_repository.py:295,369` | SQL montado por f-string/concatenação. Valores de filtro parecem parametrizados, mas o padrão é frágil — padronizar com estrutura + parâmetros |
| B703 | `core/templatetags/seguranca.py:39` | `mark_safe` de JSON — **mitigado** (pré-escape de `<>&`), manter teste de regressão |
| B104 | `acesso/views/helpers.py:84` | Bind `0.0.0.0` — apenas dev (`runserver`); garantir que produção usa ASGI (uvicorn) |

### Verificações OK ✅
- Sem segredos/tokens hardcoded (grep negativo em core/acesso/api/contatos/dashboard/gestao).
- Tabelas de token removidas (`refresh_token`, `service_token`, `auth_attempt`, `password_invite_token`, `kpi_snapshot`) sem nenhuma referência no código.
- Rate limit de login ativo (5 tentativas); JWT exclusivo da API; `viewer` sem escrita (testado na API).

## 3. SQL — risco real de integridade

**Conexão GPRB aberta com `autocommit=True`** (`core/gprb/connection.py`). Consequência: cada `execute()` comita imediatamente; o `commit()` final dos repositórios é no-op. Escritas multi-statement **não são atômicas**:

- `definir_lojas_membro` (repositories/gprb_repository.py:175): `SELECT` → `DELETE member_loja` → N× `INSERT` → `UPDATE member`. **Se um INSERT falhar no meio, o membro fica com vínculos parcialmente apagados** (perda de dados do vínculo N:N).
- Mesmo padrão em `atualizar_loja`, `criar_prefeitura`, `atualizar_prefeitura`, seed de pagamentos.

**Correção**: transação explícita (`BEGIN … COMMIT` ou `connection.transaction()`) em toda escrita multi-statement.

### Outros
- SQL duplicado em 3 camadas: `repositories/gprb_repository.py` vs `dashboard/repositories/gprb_repository.py` vs `core/gprb/*` (ex.: `membros_por_situacao` ×2, `listar_lojas` ×2, `listar_prefeituras` ×2).
- `coluna_existe()` executado em requisições quentes (defesa contra schema legado que não existe mais no banco novo — remover após verificação).
- Busca com `LIKE '%termo%'` sem `ILIKE`/normalização em listas (case-sensitivity inconsistente) — revisar nos filtros.

## 4. Duplicação e código morto

| Item | Local | Ação |
|------|-------|------|
| App morto inteiro | `export_dashboard/` (views de 526 linhas) | Ninguém importa → remover |
| Módulo morto | `core/gprb_read.py` | Ninguém importa → remover |
| SQL duplicado | repos de contatos vs dashboard vs core/gprb | Consolidar fonte única |
| `_txt`, `_sem_acento`, `_rodape` | ×2 arquivos | Extrair para utilitário comum |
| `backfill_tenant_id` | ×2 management commands | Consolidar |
| `exportar_csv` | ×2 views | Utilitário compartilhado |
| View funcs genéricas | `lista`/`editar`/`excluir` ×3 apps | Padrão por app — aceitável, não priorizar |

## 5. Performance

- Dashboard: **12 queries GPRB por render** (mitigado por cache `DashboardCache` + conexão thread-local). Otimizar agregando em CTEs quando tocar nos painéis.
- Paginação na lista de membros: OK (25/página) ✅.
- `coluna_existe` por request: remover (ponto quente).
- Índices: `member_loja("lojaId")` existe ✅; revisar índices de filtro frequentes (`member.situacao`, `loja."prefeituraId"`) com EXPLAIN quando houver volume de dados.

## 6. Mapeamento para as specs de correção

| Spec | Problemas endereçados |
|------|----------------------|
| `specs/001-problema-autenticacao` | BOM tarefas/views, B104, endurecimento de sessão/tokens, testes de auth web |
| `specs/002-problema-pagamento` | Transações atômicas (bloqueia Financeiro), B608 dos repos, padrão de escrita — base p/ `specs/001-financeiro-anuidades` |
| `specs/003-problema-estoque` | Estado do módulo (removido por decisão) + remanescentes |
| `specs/004-problema-relatorio` | Cópia morta export_dashboard, ranking_dados E(33), exportar_csv duplicado, queries do dashboard |
| `specs/005-problema-permissoes` | _montar_contexto F(45), equipe D(28), centralização de RBAC web, testes de permissão web |

*Cross-cutting*: BOM/complexidade de views distribuídas em 001/004/005; SQL/B608 consolidados em 002 como padrão da casa.

## 7. Execução das correções — status (03/10/2026)

| Spec | Status | Evidências |
|------|--------|------------|
| 001-autenticacao | ✅ executada | BOM removido; B104 = falso positivo (`# nosec B104` em `client_ip`); `test_login_web.py` (7) + `test_ativacao_web.py` (6) verdes |
| 002-pagamento (transações) | ✅ executada | `gprb_transaction()` + 10 escritas atômicas; ZERO commits soltos; 7× B608 resolvidos (0 MEDIUM na camada GPRB); `test_gprb_transaction.py` (3) + `test_gprb_writes.py` (5) — rollback comprovado |
| 003-estoque | ⏸ aguarda decisão de produto | Módulo inexistente; zero remanescentes; dados antigos em backup |
| 004-relatorio | ✅ T1–T3 (T4 opcional pendente) | `export_dashboard/` + `core/gprb_read.py` removidos (grep vazio); `ranking_dados` E(33) → helpers ≤ C (`radon -n D` vazio); CSV já compartilha `core.utils.csv_seguro/resposta_csv` |
| 005-permissoes | ✅ T1–T5 | `_montar_contexto` F(45) → 7 helpers ≤ C; `_processar_etapa` D e view `equipe` D decompostos; `test_rbac_web.py` (8) verde; `qs_escopo` fonte única; `scripts/audit_decorators.py` → "OK" |

### Ferramentas re-executadas (03/10/2026)

- **radon**: zero F/E/D em `core/gprb/ranking.py`, `acesso/views/config.py`, `acesso/views/equipe.py`; módulos novos ≤ C (`contatos/views/gprb_prefeituras.py`).
- **bandit**: 0 achados nos arquivos novos/alterados (padrão literal + `.replace('{where}', where)` + `# nosec B608` na linha do execute).
- **audit_decorators**: todas as rotas (exceto allowlist) com decorator de autenticação.
- **pytest** (arquivos selecionados — suíte completa excede 10 min no ambiente): 50 + 14 tests verdes.

### Regressão pega e corrigida nos testes

- `guard_equipe` deixava `admin_saas` sem tenant ver a equipe de todos (`qs_escopo(None)` sem filtro) — agora exige tenant (`test_admin_saas_sem_tenant_nao_acessa_equipe` verde).
- Form de Potência coletava e-mail que era descartado (tabela sem coluna) — coluna `email` criada e persistida.

### Feature nova (03/10/2026) sobre a base corrigida

- **Potência**: contatos de Secretária/Tesouraria (e-mail + telefone), PIX, valor e vencimento da anuidade — schema (`prefeitura`), repositório (sem `coluna_existe`), CRUD e tabela da listagem atualizados.
- ~~**Emolumentos**~~: módulo removido (05/10/2026) — a tabela `emolumento` foi dropada e as views/URLs/menu substituídos pelo upload de PDF de valores por loja.
- Migração idempotente em `scripts/aplicar_schema_potencia.py` (aplica em `saldabritanea` e `saldabritanea_test`).
