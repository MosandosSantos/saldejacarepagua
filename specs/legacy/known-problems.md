# Problemas conhecidos (legado/atual)

> Inventário honesto do que está quebrado, parcial ou frágil em outubro/2026. Atualizar a cada descoberta.

## 🔴 Ambiente / infraestrutura

| # | Problema | Impacto | Mitigação atual |
|---|----------|---------|-----------------|
| 1 | **Docker/WSL quebrados no boot** ("context deadline exceeded") | Sem Docker no dev | PostgreSQL 17 **nativo**; deploy em VPS (Docker Compose) segue disponível |
| 2 | **Servidor sem auto-reload** (`--noreload` na 8888) | Editar código exige restart manual | `taskkill //F //PID` + subir de novo (comando em `DOCS/README.md`) |
| 3 | PATH do uv/specify só vale em terminal novo | `specify` não resolve em sessão aberta antes da instalação | `export PATH="$USERPROFILE/.local/bin:$PATH"` ou reabrir terminal |

## 🟠 Funcional — quebrado ou parcial

| # | Problema | Impacto | Situação |
|---|----------|---------|----------|
| 4 | **Financeiro é placeholder** | Rota e item de menu existem; módulo sem função real | Especificar (spec-driven) sobre `payment`/`payment_period`/`payment_status` — spec em `specs/financeiro/spec.md` |
| 5 | **Banco novo vazio** | Sistema operável mas sem dados de negócio | Importar histórico do `saldogprb` ou cadastrar do zero |
| 6 | Bancos antigos (`saldogprb`, `esferasda_crm`) ainda existem | Risco de leitura errada/confusão | Desligados no `.env`; exclusão física só após validação |
| 7 | `esferasda` é de outro sistema (obras) | Risco de DROP acidental | Regra: nunca tocar |

## 🟡 Dívida técnica

| # | Problema | Impacto | Situação |
|---|----------|---------|----------|
| 8 | **Camada GPRB sem testes automatizados** | Regressões só aparecem manualmente | **Bem avançado (03/10/2026):** 64 tests verdes cobrindo escritas/transactions (`test_gprb_writes`, `test_gprb_transaction`), login web (`test_login_web`, `test_ativacao_web`), RBAC web (`test_rbac_web`, `test_equipe`) e potência (`test_potencia_web`); falta cobertura de dashboard/membros |
| 9 | ~~Métodos mortos legados (`export_dashboard/` e `core/gprb_read.py`)~~ | — | ✅ **Removidos** (03/10/2026, spec 004-T1); grep vazio |
| 10 | `.env` sensível + histórico de corrupção por sed | Cuidado ao editar | Editar via script Python |
| 11 | Rate limit de login (5 tentativas) é **volátil** — contador em cache do Django, zerado a cada reinício do servidor | Atacante pode reiniciar... não: reinício só via servidor; impacto real é apenas conveniência operacional (bloqueio temporário de admin em E2E) | **Aceito para v1** (decisão 2026-10-02): banco localhost single-tenant e janela curta tornam persistência desnecessária; se exposto publicamente, migrar contador para banco (task futura) |
| 12 | Diretórios legados no repo (`_legacy/`, `venv/`+`.venv/` duplicados, `node_modules/`, `db.sqlite3`, `aula4.sql`, `dashboard_completo.tar.gz`) | Repositório poluído | Limpeza/discussão futura |
| 13 | Docs antigas na raiz (`README.md` raiz, `PRODUCT.md`, `systemdesign.md`, `DESIGN.md`) desatualizadas (falam de banco `gprbr`, porta 8000, nichos de saúde como foco) | Confusão para novos devs | Docs canônicas agora em `DOCS/README.md` + `DOCS/PRD.md` + `specs/`; atualizar ou marcar como legacy |
| 14 | Utilitários duplicados com semânticas distintas: `_txt` ×2, `_sem_acento` ×2 (NFD vs mapa manual), `_rodape` ×2 | Manutenção dupla; mesclar mudaria comportamento — precisa unificar com cuidado | Documentado no code-audit; mesclar só com testes de equivalência |
| 15 | `acesso/views/config.py` ainda tem 616 LOC (funções agora pequenas, arquivo grande) | Arquivo grande, mas complexidade por função ≤ C | Quebrar em módulos quando tocar em config |
| 16 | Dashboard faz 12 queries GPRB por render (spec 004-T4 opcional) | Custo ok com cache + conexão thread-local | Agregar em CTEs quando tocar nos painéis |

## 🟢 Histórico — resolvidos nesta migração (referência)

| Problema | Resolução |
|----------|-----------|
| `atualizar_membro` gerava SQL com aspas duplas do form | Corrigido |
| `_preparar_membro_para_form` com chaves erradas (datas nunca preparavam) | Corrigido |
| KeyError `abbr` no dashboard (repo retornava `abbreviation`) | Alias no SQL |
| `ranking_lojas` usava coluna `l.name` inexistente | `COALESCE("nomeFantasia", ...)` |
| Rankings retornavam chaves `name`/`total` e templates esperavam `nome`/`rank`/`total_mx` | Repo agora devolve chaves do template |
| `potencia.nome` `varchar(6)` não comportava 'GLMMMRJ' | Alargado para `varchar(50)` |
| member_loja recriada no desenho N:N correto (com `dataInclusao`) + backfill 751 linhas | Feito no banco antigo; desenho replicado no `saldabritanea` |
| Classes (MX/EN/CBCS) e `prefeitura.regiao` espalhadas pelo código | Removidos de banco, CRUD e templates |
| Tabela `session` referenciada por painéis do dashboard sem nunca ter existido | `proximas_sessoes`/`agendamento_lojas` repontados para a tabela `meeting` (dataSessao/tipo/titulo); log limpo, painéis funcionais |
| BOM U+FEFF em `tarefas/views.py` quebrava radon/bandit | Removido (spec 001-T1) |
| Rank F(45) `_montar_contexto`, ranks E(35/33) `buscar_membro`/`ranking_dados`, 11× rank D | Decompostos (specs 002/004/005); radon sem F/E/D nos arquivos tocados |
| B608 ×7 (SQL assembly na camada GPRB) | Resolvidos (spec 002): transação explícita + padrão literal+`.replace()` — 0 MEDIUM bandit na camada |
| RBAC web sem testes e view `equipe` sem decorator | `test_rbac_web.py` (8 tests) + `@web_login_required` + audit_decorators OK (spec 005) |
| Guard `equipe` deixava admin_saas sem tenant listar todos os usuários (regressão da 005, pega pelos testes) | `guard_equipe` agora exige tenant; 50/50 verde |
| E-mail do form de Potência era descartado (tabela sem coluna `email`) | Coluna criada + CRUD completo de contatos de cargo, PIX e anuidade (feature 03/10) |

> Regra de ouro: qualquer novo problema descoberto entra aqui **antes** do fix, com impacto e mitigação.
