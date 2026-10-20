# Bloqueios residuais da suíte de testes (papéis legados B2 + mismatches do WIP) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Levar a suíte de testes de 454 passed / 209 failed / 48 skipped / 19 errors para verde incremental, corrigindo (a) o uso semântico de papéis aposentados nos testes, (b) os contratos WIP de Loja/Vale/admin-SaaS/templates, (c) o teste de PDF grande no Windows e (d) priorizando o inventário restante em gates executáveis.

**Architecture:** Quatro frentes dependentes. (A) Papéis: definir o papel atual correto por asserção (`viewer` para leitura, oficialato/`ROLE_DELEGADO` para escrita de tenant, `admin_saas` + `admin_tenant_id` para administração de tenant) e migrar fixtures/call sites. (B) Contratos WIP: cada falha é resolvida contra o spec que originou o teste — quando o spec confirma o teste, corrige-se produto/template; quando não, mantém-se ponto de decisão. (C) PDF: eliminar o node id gigante da parametrização preservando a cobertura de 10 MB. (D) Triage: rodar o inventário por gates temáticos e reproduzir sob `--create-db` antes de editar, para separar falha real de contaminação do banco de teste.

**Tech Stack:** Django 6.0.8, pytest 9.0.1 + pytest-django, PostgreSQL nativo (`127.0.0.1:5432`, banco alvo `gprbr_test`), Windows.

**Spec:** `DOCS/superpowers/specs/2026-10-12-suite-teste-bloqueios-pre-existentes-design.md`
**Specs de origem consultados (a frente argumenta a partir deles):**
- `DOCS/superpowers/specs/2026-10-11-vale-tenant-isolation-design.md`
- `DOCS/superpowers/specs/2026-10-11-local-vale-contacts-design.md`
- `DOCS/superpowers/specs/2026-10-08-retire-tenant-roles-and-potency-pdf-design.md`
- `DOCS/superpowers/plans/2026-10-08-retire-tenant-roles-and-saas-admin.md`
- `DOCS/superpowers/plans/2026-10-12-suite-teste-bloqueios-pre-existentes.md` (plano raiz, Task 5)

**Artefatos de evidência (ler, não reexecutar a suíte completa):**
- Baseline: `DOCS/superpowers/plans/2026-10-12-suite-teste-baseline.txt` (454 passed / 209 failed / 48 skipped / 19 errors; 6 collection + 13 execution).
- Task 4 (após desbloquear 6 módulos): `.superpowers/sdd/2026-10-12-suite-teste-bloqueios-pre-existentes/task-4-report.md` (36 passed / 6 failed / 2 errors; 44 itens coletados).
- Saída completa da Execução 2 (7022 linhas) preservada em `%TEMP%\opencode\t2_full_run.txt`; a lista crua de IDs está em `%TEMP%\opencode\t2_failed_lines.txt` (209 `FAILED` + 19 `ERROR`).

## Global Constraints

- Django `6.0.8`; pytest `9.0.1`.
- Papéis atuais (`acesso/models.py`): `ROLE_ADMIN_SAAS='admin_saas'` (global, sem tenant), `ROLE_VIEWER='viewer'` (somente leitura, único em `ROLES_DE_TENANT`), `ROLE_ADM='ADM'` (admin global — vê todos os Vales ativos em `contatos/views/vales.py::_vales_do_request`), `ROLE_TESOUREIRO`, `ROLE_SECRETARIO`, `ROLE_DELEGADO='delegado'` (editor escopado por tenant), `ROLE_PRESIDENTE_CORPO`. Aposentados e **ainda presentes como constantes mortas**: `ROLE_ADMIN_COMPANY='admin_company'`, `ROLE_OPERACIONAL='operacional'` (`acesso/models.py:8-9`).
- `ROLES_QUE_EDITAM` (editores) = `ROLE_ADMIN_SAAS` + oficialato (`ADM`, `tesoureiro`, `secretario`, `delegado`, `presidente_corpo`); **`viewer` não edita** (`acesso/decorators.py::web_requer_edicao`).
- Gerir Vale/Loja = `admin_saas` ou `ADM` (`_pode_gerir_vale`, `_pode_criar_loja`, `_pode_excluir_loja`); alterar = inclui `ROLE_DELEGADO`/`ROLE_PRESIDENTE_CORPO`.
- **Nenhuma mudança de comportamento de produto sem spec/autorização**. Os specs acima são a autorização; fora deles, virar ponto de decisão.
- **Não enfraquecer isolamento de tenant.** Testes de "outro tenant" permanecem com papel escopado (`ROLE_DELEGADO`/`ROLE_VIEWER`) e asserções 404/403 intactas.
- **Não editar `teste/test_role_retirement.py` nem `teste/test_role_retirement_migration.py`**: eles usam `admin_company`/`operacional` de propósito para validar a migração. Onde falharem, registrar como ponto de decisão de produto (migração/middleware), não "corrigir" a string.
- **Não tocar nos ~248 arquivos WIP** fora dos caminhos listados em cada task; não fazer `git add -A`.
- Banco de teste por variável de ambiente (o valor real é local e **nunca** entra em git/plano). O operador deve definir antes de rodar:
  ```powershell
  # Senha local do Postgres nativo; obter do cofre/ambiente do operador. NÃO commitar.
  $env:VALE_TEST_DATABASE_URL='postgresql://postgres:<SENHA_LOCAL>@127.0.0.1:5432/gprbr_test'
  ```
  `core/settings_vale_test.py` valida esse alvo (`_ci_target`) e aponta o banco de teste para `test_saldabritanea_vales`.
- **Reprodução controlada:** após mudanças de migration/schema, usar `-o addopts='' --create-db`; depois `--reuse-db`. Nunca rodar `--create-db` concorrente com outra sessão no mesmo banco.
- Testes focados usam `teste/` e `-q --no-header`; **não rodar a suíte inteira** (já custou 36:58).

## Review Focus

- **`admin_saas` sem tenant selecionado não pode mutar Vale/Loja de tenant** — hoje `_vales_do_tenant_para_edicao`/`_lojas_visiveis` devolvem todos os registros globais para `admin_saas`/`ADM`; o esperado (spec de isolamento) é bloqueio (403) quando há escopo de tenant, sem vazar existência de objeto.
- **Formulário de Loja não pede Vale arbitrário** — o tenant ativo determina o Vale (spec de isolamento, seção "Interface e compatibilidade"); o WIP exige `POST['vale_id']` para `admin_saas`.
- **Lista local de Membros não exibe indicadores dependentes de GPRB** (anuidade/presenças) — a spec de isolamento manda omitir ou marcar indisponível, não mostrar zeros/filtros fictícios.
- **Listagem/confirmação de Vale mostra nome/e-mail/telefone de Secretaria e Tesouraria** (spec de local-vale-contacts, critério 4) — `prefeituras.html` ainda renderiza `p.prefeito`/`p.telefone`.
- **Teste de PDF grande continua reprovando >10 MB com `erro=tamanho`** e passa a rodar no Windows sem node id de 10 MB.

---

## Fase A — Substituição semântica de papéis aposentados nos testes

Módulos com dívida de papel (grep por `admin_company|operacional|ROLE_OPERACIONAL|ROLE_ADMIN_COMPANY|usuario_operacional|headers_operacional`):
`teste/conftest.py`, `test_auth_api.py`, `test_ativacao_web.py`, `test_equipe.py`, `test_fase_b_config.py`, `test_fase_j_lead_orcamento_metas.py`, `test_fase_k_timestamps.py`, `test_rbac_api.py`, `test_rbac_web.py`, `test_viewer.py`, `test_atividades_view.py`, `test_contatos_api.py`, `test_comunicacao.py`, `test_campos_personalizados.py`, `test_cache_invalidation.py`, `test_dashboard_avancado.py`, `test_fase_a_funil.py`, `test_fase_f_pipeline.py`, `test_fase_g_tarefas.py`, `test_fase_i_automacoes.py`, `test_fase_n_carteiras.py`, `test_fase_o_email_avancado.py`, `test_fase_r_lead_rapido.py`, `test_leads_view.py`, `test_import_view.py`.

### Ponto de decisão A-DP1 (bloqueante de A3/A4) — retirada de papéis está pela metade no produto

Verificação feita no código atual:
- `acesso/models.py:8-9` mantém `ROLE_ADMIN_COMPANY`/`ROLE_OPERACIONAL`; `:202` (`Usuario.pode_transferir_dono`) usa `ROLE_ADMIN_COMPANY`.
- `acesso/views/config.py` usa `ROLE_ADMIN_COMPANY` em 11 pontos (ex.: `:381`, `:483-485`, `:493`) e **não** aceita `admin_saas` com tenant selecionado.
- `contatos/management/commands/seed_dados.py:22-23,237-238,388` ainda cria papéis aposentados.

Consequência: trocar a fixture `admin_company` por `admin_saas` + `admin_tenant_id` faz os fluxos de administração de tenant (`/equipe/`, `/config/`) falharem em produto, porque `config.py` exige literalmente `admin_company`. As Tasks 3 e 5 do plano de aposentadoria (`DOCS/superpowers/plans/2026-10-08-retire-tenant-roles-and-saas-admin.md`) **descrevem** essa migração, mas não foram executadas.

> **Decisão exigida antes de A3/A4.** Opção (i): executar primeiro as Tasks 3/5 do plano de aposentadoria (mover as checagens de `ROLE_ADMIN_COMPANY` para o predicado `admin_saas` + `resolve_tenant_id`, remover as constantes mortas) — é o que a spec `2026-10-08-retire-tenant-roles...` autoriza, mas sobrepõe um projeto à parte e muda produto. Opção (ii): manter `admin_company` nas fixtures de administração de tenant e só migrar os testes de leitura/negativos → a Fase A fica parcial e há dívida remanescente. **Recomendação: (i)**, com autorização explícita do dono do plano-raiz. Enquanto A-DP1 não estiver resolvido, A3/A4 ficam bloqueados (A1/A2 e a Fase B/C/D seguem).

### Task A1: Fixtures e mapa de substituição

**Files:**
- Modify: `teste/conftest.py:72-125`
- Create (mapa, versionar): `DOCS/superpowers/plans/2026-10-12-role-test-mapping.md`

**Interfaces:**
- Produz fixtures com nomes atuais: `usuario_viewer`/`usuario_viewer_beta` (role `viewer`), `usuario_editor`/`usuario_editor_beta` (role `delegado`), `admin_saas_tenant`/`headers_admin_saas_tenant` (`admin_saas` sem tenant, sessão com `admin_tenant_id` do tenant pedido).
- Mantém `usuario_operacional*`, `admin_company`, `headers_*` legados como **aliases depreciados** durante a migração, para permitir commits incrementais; a remoção fica na Task A5 (encerramento da Fase A, após A2/A3/A4).

- [ ] **Step 1: Escrever o mapa de substituição**

Em `DOCS/superpowers/plans/2026-10-12-role-test-mapping.md`, tabela por arquivo/teste com a coluna "papel atual" escolhida (uma linha por teste onde a escolha não é óbvia). Regra default:

| legado | substituto | uso |
|---|---|---|
| `usuario_operacional` (leitura/negativo `test_operacional_nao_*`) | `usuario_viewer` (`ROLE_VIEWER`) | não edita; 302/403 esperados |
| `usuario_operacional` (cria/edita dados do tenant) | `usuario_editor` (`ROLE_DELEGADO`) | editor escopado por tenant |
| `usuario_operacional_beta` | `usuario_viewer_beta` / `usuario_editor_beta` | idem, tenant beta |
| `admin_company` | `admin_saas_tenant` (`admin_saas`, sessão `admin_tenant_id`) | administração do tenant — **depende de A-DP1** |
| `headers_operacional` | `headers_viewer` (leitura) / `headers_editor` (escrita) | API |
| `headers_admin_company` | `headers_admin_saas_tenant` | API admin do tenant — **depende de A-DP1** |
| string `'operacional'`/`'admin_company'` em POST/`papel`/`role` | valor atual conforme a asserção (`'viewer'`,`'delegado'`,`'admin_saas'`) | validação |

### Task A2: Testes de autenticação/RBAC por papel (independente de A-DP1)

**Files:**
- Modify: `teste/conftest.py` (só as fixtures acima)
- Modify: `teste/test_auth_api.py:22,57`
- Modify: `teste/test_rbac_api.py`
- Modify: `teste/test_rbac_web.py`
- Modify: `teste/test_viewer.py`

**Interfaces:**
- Consumes: fixtures de A1.
- Produces: `/api/v1/auth` e RBAC verdes refletindo papéis atuais.

- [ ] **Step 1: Estabelecer falhas (RED)**

Run (definir `$env:VALE_TEST_DATABASE_URL` conforme Global Constraints):
```powershell
python -m pytest teste/test_rbac_api.py teste/test_rbac_web.py teste/test_viewer.py -q --no-header -o addopts='' --create-db
```
Expected: 6 falhas em `test_rbac_api` (`::test_admin_saas_cria_admin_company`, `::test_admin_saas_cria_operacional`, `::test_admin_company_sem_tenant_rejeitado`, `::test_operacional_sem_tenant_rejeitado`, `::test_tenant_inexistente_rejeitado`, `::test_email_duplicado_rejeitado`), 1 em `test_rbac_web::test_admin_company_gerencia_equipe`, e `test_viewer::test_viewer_nao_ve_botoes_de_edicao` + `::test_admin_saas_continua_editando_na_web` + `::test_api_admin_saas_cria_viewer` (+1 ERROR `::test_api_viewer_le_mas_nao_escreve`).

- [ ] **Step 2: Ajustar asserções para papéis atuais**

- `test_auth_api.py`: `assert ...['role'] == 'operacional'` → `'viewer'` (a fixture `usuario_operacional` vira `usuario_viewer` em A1).
- `test_rbac_api.py`:
  - `test_admin_saas_cria_admin_company` / `test_admin_saas_cria_operacional`: renomear para `*_rejeita_papel_aposentado` e assertar `422` (a API já rejeita o papel — validar contra `test_role_retirement.py::test_removed_roles_are_not_assignable`).
  - `test_admin_company_sem_tenant_rejeitado` / `test_operacional_sem_tenant_rejeitado`: literalmente `test_<papel>_sem_tenant_rejeitado` → `test_papel_atual_sem_tenant_rejeitado`, criando com papel atual válido sem tenant e assertando `422`.
  - `test_tenant_inexistente_rejeitado`, `test_email_duplicado_rejeitado`: trocar `role='operacional'` por `'viewer'` e `tenant_id` válido.
- `test_rbac_web.py::test_admin_company_gerencia_equipe`: usar `admin_saas_tenant` (depende de A-DP1) ou `usuario_editor` se a intenção for apenas "oficialato edita".
- `test_viewer.py`: `test_api_admin_saas_cria_viewer` espera `409` → reproduzir e corrigir o conflito (email/tenant), preservando a asserção de criação; `test_viewer_nao_ve_botoes_de_edicao` e `test_admin_saas_continua_editando_na_web` — corrigir o autor das páginas conforme papel do spec (`viewer` não vê botões; `admin_saas` selecionado continua editando).

- [ ] **Step 3: Verificar (GREEN)**

Run: `python -m pytest teste/test_auth_api.py teste/test_rbac_api.py teste/test_rbac_web.py teste/test_viewer.py -q --no-header -o addopts='' --create-db`
Expected: PASS (o ERROR de `test_api_viewer_le_mas_nao_escreve` pode ser ponto de decisão se for FK de tenant; registrar causa antes de qualquer edição).

- [ ] **Step 5: Commit**

```bash
git add teste/conftest.py teste/test_auth_api.py teste/test_rbac_api.py teste/test_rbac_web.py teste/test_viewer.py DOCS/superpowers/plans/2026-10-12-role-test-mapping.md
git commit -m "test: mapear papeis atuais em auth/rbac/viewer"
```

### Task A3: Fluxos de administração de tenant (depende de A-DP1)

**Files:**
- Modify: `teste/test_equipe.py`, `teste/test_ativacao_web.py`, `teste/test_fase_b_config.py`, `teste/test_fase_k_timestamps.py`, `teste/test_comunicacao.py` (usos de `admin_company`)
- Modify (se A-DP1 = opção i): `acesso/views/config.py`, `acesso/models.py`, `contatos/management/commands/seed_dados.py`
- Test: `teste/test_equipe.py`

**Interfaces:**
- Consumes: `admin_saas_tenant`/`headers_admin_saas_tenant` de A1; `resolve_tenant_id` (`acesso/tenant_context.py`) e `web_requer_tenant_context` (`acesso/decorators.py`).
- Produces: fluxos de `/equipe/`/`/config/` funcionando para `admin_saas` com tenant selecionado e para oficialato; `viewer` bloqueado.

- [ ] **Step 1: Falhas (RED)** — `python -m pytest teste/test_equipe.py teste/test_ativacao_web.py teste/test_fase_b_config.py teste/test_fase_k_timestamps.py -q --no-header -o addopts='' --create-db`; Expected: `test_equipe` 8 falhas (`test_admin_company_acessa_equipe`, `test_admin_company_cadastra_operacional`, `test_convite_isolado_por_tenant`, `test_email_duplicado_rejeitado`, `test_papel_invalido_rejeitado`, `test_admin_company_exclui_contato`, `test_admin_company_exclui_nota`... confirmar pelo artefato), `test_fase_b_config::test_admin_cria_convite_e_gera_link`, `test_fase_k::test_equipe_mostra_criado_em`.
- [ ] **Step 2: Se A-DP1=(i), completar a retirada** — trocar em `config.py` o gate `role == ROLE_ADMIN_COMPANY and tid is not None` por predicado `admin_saas` + `resolve_tenant_id(request)` (ver plano de aposentadoria Task 3, Step 4); remover as constantes mortas de `models.py` e `seed_dados.py`. Preservar perfil/senha/tema como estão.
- [ ] **Step 3: Migrar fixtures/call sites** — `admin_company`→`admin_saas_tenant`; `usuario_operacional` negativos→`viewer`, escritas→`usuario_editor`; strings `papel='operacional'`→`'viewer'`/`'delegado'`; `ROLE_OPERACIONAL` (import) → papel atual em `test_ativacao_web`.
- [ ] **Step 4: GREEN** — repetir o comando do Step 1; Expected: PASS (isolamento de `test_convite_isolado_por_tenant` preservado).
- [ ] **Step 5: Commit** — `git add` dos arquivos tocados; `git commit -m "test: migrar fluxos admin de tenant para admin_saas selecionado"`.

### Task A3b: Registrar a dívida residual de `test_role_retirement*` (sem editar os arquivos)

**Files:**
- Modify (documento): `DOCS/superpowers/plans/2026-10-12-suite-teste-residuais.md` (seção de concerns) ou `DOCS/superpowers/plans/2026-10-12-role-test-mapping.md`

**Interfaces:**
- Consumes: achados de A-DP1.
- Produces: ponto de decisão explícito, sem alterar os testes legados.

- [ ] **Step 1: Reproduzir e catalogar** — `python -m pytest teste/test_role_retirement.py teste/test_role_retirement_migration.py -q --no-header -o addopts='' --create-db`. Foi observado no baseline: `test_role_retirement::test_existing_api_token_uses_migrated_viewer_role`, `test_role_retirement_migration::test_existing_admin_saas_tenant_is_cleared`, `::test_existing_browser_session_uses_migrated_viewer_role` e ERROR em `::test_migration_converts_retired_users_and_pending_invites_to_viewer` (IntegrityError ao inserir `Convite` legado no estado 0018).
- [ ] **Step 2: Não editar as strings legadas.** Registrar no mapa se a causa é produto (migração 0019/middleware de sessão) ou estado do banco de teste (fila de transação com dados de execução anterior). Se for produto, encaminhar para o projeto de aposentadoria; se for estado, cobrir com `--create-db` e re-checar.
- [ ] **Step 3: Commit** — `git commit -m "docs(plans): registrar decisao de test_role_retirement"`.

### Task A4: Fluxos de escrita que usavam `usuario_operacional` (depende de A-DP1, se houver administração)

**Files:**
- Modify: `teste/test_atividades_view.py`, `test_contatos_api.py`, `test_campos_personalizados.py`, `test_cache_invalidation.py`, `test_dashboard_avancado.py`, `test_fase_a_funil.py`, `test_fase_f_pipeline.py`, `test_fase_g_tarefas.py`, `test_fase_i_automacoes.py`, `test_fase_j_lead_orcamento_metas.py`, `test_fase_n_carteiras.py`, `test_fase_o_email_avancado.py`, `test_fase_r_lead_rapido.py`, `test_leads_view.py`, `test_import_view.py`

**Interfaces:**
- Consumes: `usuario_editor`/`headers_editor` (role `delegado`) para escrita de tenant; `usuario_viewer` para negativos.
- Produces: suítes de feature usando papéis atuais.

- [ ] **Step 1: Falhas (RED)** — repetir por módulo/gate (ver Fase D). Não corrigir produto aqui: o objetivo é **atribuir** cada `403`/`302` a (papel aposentado) vs (produto/WIP) vs (estado do banco).
- [ ] **Step 2: Trocar a fixture** — onde o teste representa um usuário do tenant que cria/edita, usar `usuario_editor`/`headers_editor`; onde é negativo (`test_operacional_nao_*`, `test_viewer_*`), usar `usuario_viewer`; onde é admin de tenant, `admin_saas_tenant`.
- [ ] **Step 3: GREEN por gate** — rodar o gate correspondente da Fase D e confirmar a queda de falhas atribuídas a papel.
- [ ] **Step 4: Commit** — `git commit -m "test: migrar fixtures de papel para viewer/editor/admin_saas"`.

### Task A5: Remover os aliases depreciados (encerramento da Fase A)

**Files:**
- Modify: `teste/conftest.py` (remover `usuario_operacional*`, `admin_company`, `headers_operacional`, `headers_admin_company` legados)
- Grep de controle: todo `teste/` por `usuario_operacional|admin_company|headers_operacional|headers_admin_company`

**Interfaces:**
- Consumes: aliases criados em A1, já sem consumidores após A2/A3/A4.
- Produces: `conftest.py` apenas com fixtures atuais (`usuario_viewer*`/`usuario_editor*`/`admin_saas_tenant`/`headers_*` atuais), sem alias depreciado.
- Dependência: A5 só fecha depois de A2/A3/A4. Se A-DP1 = opção (ii) mantiver `admin_company` nos testes de administração de tenant, A5 fica **parcial** (remover só o que já migrou) ou bloqueada — registrar o saldo em vez de forçar a remoção.

- [ ] **Step 1: Confirmar ausência de consumidores** — `rg -n "usuario_operacional|admin_company|headers_operacional|headers_admin_company" teste/ --glob "!test_role_retirement*.py"`; Expected: 0 ocorrências. Se houver, voltar à task de migração correspondente (A2/A3/A4) antes de remover.
- [ ] **Step 2: Remover os aliases** — apagar as definições de alias em `teste/conftest.py`, preservando as fixtures atuais. **Não** tocar em `teste/test_role_retirement*.py`, que usam as strings legadas de propósito.
- [ ] **Step 3: GREEN** — `python -m pytest teste/test_auth_api.py teste/test_rbac_api.py teste/test_rbac_web.py teste/test_viewer.py -q --no-header -o addopts='' --reuse-db`; Expected: PASS (nenhuma fixture ausente).
- [ ] **Step 4: Commit** — `git add teste/conftest.py`; `git commit -m "test: remover aliases depreciados de papel aposentado"`.

---

## Fase B — Contratos WIP: Loja, Vale, admin-SaaS e templates

Falhas residuais do Task 4 (6 failed + 2 errors) e checagem contra spec. Cada task confirma se o teste ou o produto está certo **antes** de editar.

### Task B1: Listagem de Vale exibe Secretaria e Tesouraria

> **Execução 2026-10-18:** B1 aplicada. RED confirmado ('Secretário da consulta' ausente), colunas
> `Delegado`/`Telefone` substituídas por `Secretaria`/`Tesouraria` (nome + e-mail/telefone abaixo,
> composição mobile-safe), `teste/test_vale_templates.py` 4 passed. Commit adiado (WIP compartilhado).

**Files:**
- Modify: `contatos/templates/contatos/prefeituras.html:40-41`
- Test: `teste/test_vale_templates.py::test_consult_lists_complete_contact_details_without_gprb_counts`

**Interfaces:**
- Consumes: chaves já presentes em `_para_contexto_vale` (`contatos/views/vales.py:117-142`): `secretario_nome/email/telefone`, `tesoureiro_nome/email/telefone`.
- Produces: listagem com os dois grupos de contato.

- [ ] **Step 1: RED** — `python -m pytest "teste/test_vale_templates.py::test_consult_lists_complete_contact_details_without_gprb_counts" -q --no-header -o addopts='' --reuse-db`; Expected: FAIL em `assert 'Secretário salvo'...`.
- [ ] **Step 2: Corrigir o template** — substituir as duas colunas `p.prefeito`/`p.telefone` por células que exibem, para Secretaria e Tesouraria, **nome em uma linha + e-mail/telefone abaixo** (spec `2026-10-11-local-vale-contacts-design.md`, critério 4; spec de isolamento, "Interface e compatibilidade" — quebra segura em larguras menores). Manter as asserções `'Total de lojas'/'Total de membros'/'lojas-json'` satisfeitas (não introduzir essas strings).
- [ ] **Step 3: GREEN** — mesmo comando; Expected: PASS.
- [ ] **Step 4: Commit** — `git add contatos/templates/contatos/prefeituras.html`; `git commit -m "fix(vale): listar contatos completos de secretaria e tesouraria"`.

### Task B2: Lista local de Membros sem filtros/indicadores GPRB

> **Execução 2026-10-18:** B2 **supersede**. O WIP (teste/test_membro_local.py) passou a
> documentar `Anuidade`/`Presenças` como presentes por contrato, e a lista migrou de `/contatos/`
> para `/membros/` (301 permanente). Feito em vez disso: rota canônica em 12 GETs de teste,
> âncora restaurada em `test_membro_lista_corpo_vazio_mantem_filtros_atuais`, e a UI de
> **corpo** da spec 008 (5 chips com checked preservado) foi levada para `lista.html` +
> contexto `corpos_filtro` em `gprb_membros.py::membro_lista`. 21 passed. Permissão de criação
> de membro: `_pode_criar_membro` estava com decorators de view aplicados por engano e só
> admitia admin_saas/ADM; restaurado o contrato da docstring + spec 013 ("demais perfis sem
> alteração"): editores com Vale ativo do tenant criam. Também alinhado ao spec 008: membro
> aceita várias Lojas do mesmo tenant (removida a regra "única loja" do POST).

**Files:**
- Modify: `contatos/templates/contatos/lista.html:137-138,163` (e o filtro "Anuidade:" homônimo)
- Test: `teste/test_membro_local.py::test_member_list_search_and_filters_are_scoped_to_tenant`

**Interfaces:**
- Consumes: spec de isolamento (`2026-10-11-vale-tenant-isolation-design.md`, seção "Interface e compatibilidade"): indicadores dependentes de histórico GPRB (anuidade/presenças) devem ser omitidos ou marcados indisponíveis.
- Produces: `/contatos/` local sem `Anuidade:` e sem `Presenças`.

- [ ] **Step 1: RED** — `python -m pytest "teste/test_membro_local.py::test_member_list_search_and_filters_are_scoped_to_tenant" -q --no-header -o addopts='' --reuse-db`; Expected: FAIL em `assert 'Anuidade:' not in html`.
- [ ] **Step 2: Remover ou marcar indisponível** — remover da lista local de Membros **tanto** o filtro "Anuidade: todas" **quanto** o indicador `Presenças`, além das demais colunas/filtros dependentes de GPRB (ambos vivem no bloco `{% if m.lojas %}` de `lista.html`: cabeçalhos `:137-138` e valores `:163,165`). O RED parou na asserção anterior de `Anuidade:`; a asserção de `Presenças` **não foi avaliada** (não afirmar que passa) e continuará sendo emitida enquanto o bloco `{% if m.lojas %}` existir. **Não** enfraquecer o assert nem o escopo por tenant (`q`, `loja`, `uf` continuam filtrando).
- [ ] **Step 3: GREEN** — mesmo comando; Expected: PASS. Rodar também `teste/test_membro_local.py` inteiro.
- [ ] **Step 4: Commit** — `git commit -m "fix(membro): ocultar indicadores GPRB na lista local"`.

### Task B3: `admin_saas` sem tenant não edita/exclui Vale

> **Execução 2026-10-18:** B3 aplicada no workspace atual. RED confirmado (302 ≠ 403 nos dois
> testes de `test_potencia_web.py`). `_vales_do_tenant_para_edicao` (`contatos/views/vales.py`)
> agora exige `tenant_id_da_sessao` para `admin_saas`; `ADM` permanece global.
> `test_potencia_web.py` inteiro: 11 passed. Leituras globais preservadas
> (`test_admin_saas_without_tenant_can_list_all_vales`). Os 2 falhos residuais de
> `test_saas_tenant_write_scope.py` são pré-existentes e atual — ver ponto de decisão abaixo.

**Ponto de decisão B-DP2 (2026-10-18) — RESOLVIDO (opção a, autorização do dono).**
`test_unselected_admin_cannot_mutate_gprb_prefeitura` patches `contatos.views.gprb_prefeituras.repo.criar_prefeitura`, módulo que deixou de servir a
rota `/contatos/prefeitura/nova/` (agora é `vales.prefeitura_nova`, que provisiona tenant+Vale
novos e seleciona — contrato coberto e verde em
`test_potencia_web::test_unselected_admin_saas_can_create_vale_and_selects_tenant`, o mock do
teste é vazio e a resposta 200 é o caminho de erro de validação). Do mesmo modo,
`test_unselected_admin_cannot_delete_gprb_member` patches `gprb_membros.repo.*`, atributo
inexistente no módulo local. Ambos afirmam a arquitetura GPRB aposentada.
**Resolução (2026-10-18):** testes reescritos para o contrato atual —
`test_unselected_admin_cannot_edit_existing_vale` (POST de edição de Vale existente sem tenant
selecionado → 403, registro intacto) e
`test_unselected_admin_cannot_delete_member_while_vale_archived` (exclusão de membro bloqueada
pelна Vale arquivado → 403, membro intacto; consulta continua aberta conforme spec 013).
`test_saas_tenant_write_scope.py`: 15 passed.

**Files:**
- Modify: `contatos/views/vales.py:55-62` (`_vales_do_tenant_para_edicao`)
- Test: `teste/test_potencia_web.py::test_unselected_admin_saas_cannot_edit_vale`, `::test_unselected_admin_saas_cannot_delete_vale`

**Interfaces:**
- Consumes: spec de isolamento ("admin_saas ... Para abrir e alterar dados de um Vale existente, precisa selecionar o tenant correspondente"; "Tenant-scoped writes require a valid selection").
- Produces: `_vales_do_tenant_para_edicao` retornando `None` para `admin_saas` sem `admin_tenant_id` válido → 403; mantém `ADM` global (vê todos) e usuário comum escopado.

- [ ] **Step 1: RED** — `python -m pytest "teste/test_potencia_web.py::test_unselected_admin_saas_cannot_edit_vale" "teste/test_potencia_web.py::test_unselected_admin_saas_cannot_delete_vale" -q --no-header -o addopts='' --reuse-db`; Expected: FAIL `assert 302 == 403`.
- [ ] **Step 2: Corrigir a view** — para `ROLE_ADMIN_SAAS`, usar `tenant_id_da_sessao(request)`; se `None`, retornar `None` (as views já devolvem 403 em `_vales_do_request`/`prefeituras`). Não alterar `ADM` sem spec.
- [ ] **Step 3: GREEN** — comando do Step 1 + `teste/test_potencia_web.py` inteiro; preservar `test_admin_saas_without_tenant_can_list_all_vales` (leitura global) e `test_archive_vale_preserves_local_record_and_tenant`.
- [ ] **Step 4: Commit** — `git commit -m "fix(vale): exigir tenant selecionado para editar/arquivar como admin_saas"`.

### Task B4: Criação de Loja sem `vale_id` + rota de Loja do `admin_saas` sem tenant

> **Execução 2026-10-17:** B4 aplicada no workspace atual (junto ao WIP do formulário de Loja).
> Resultado: `teste/test_loja_local.py` **25 passed**; vizinhos (`test_permissoes_vale_loja`,
> `test_lojas_paginacao_exportacao`, `test_lojas_navigation`, `test_loja_web` e o restante de
> `test_saas_tenant_write_scope`) **41 passed / 2 failed / 8 skipped** — as 2 falhas restantes são
> `test_unselected_admin_cannot_mutate_gprb_prefeitura` (200 ≠ 403 no POST de Vale) e
> `test_unselected_admin_cannot_delete_gprb_member` (teste legado procura `gprb_membros.repo`,
> que não existe mais), ambas pré-existentes no baseline e fora do escopo de B4.
> Ruff/`manage.py check`/`makemigrations --check` limpos. Commit adiado: as mudanças compartilham
> arquivos com o WIP da Loja (sem commits, como nos planos 2026-10-16/17).

**Files:**
- Modify: `contatos/views/gprb_lojas.py:322-373` (`loja_nova`, `vale_id` em `:343`) e `:95-112` (`_eh_admin_global`/`_lojas_visiveis`)
- Test: `teste/test_loja_local.py::test_create_loja_uses_selected_tenant_without_posted_vale`, `::test_admin_saas_without_selected_tenant_cannot_use_loja_routes`

**Interfaces:**
- Consumes: spec de isolamento ("A tela de Loja deixa de pedir um Vale arbitrário: o tenant ativo determina o Vale"; "Lojas ... nunca usam fallback para um tenant arbitrário").
- Produces: POST de Loja sem `vale_id` usa o Vale do tenant da sessão; `admin_saas` sem seleção recebe 403 nas rotas de Loja.

- [x] **Step 1: RED** — `python -m pytest teste/test_loja_local.py -q --no-header -o addopts='' --reuse-db`; confirmado: `200`/`200` em vez de `302`/`403`.
- [x] **Step 2: Decidir e aplicar** — para `test_create_..._without_posted_vale`, default `vale_escolhido = vale_sessao` quando nenhum `vale_id` for enviado (spec confirma o teste). Para `test_admin_saas_without_selected_tenant_cannot_use_loja_routes`, `_lojas_visiveis` deve devolver `None` para `admin_saas` sem tenant selecionado (403), mantendo `ADM` global.
- [x] **Step 3: GREEN** — `teste/test_loja_local.py` inteiro: 25 passed; preservados `test_loja_form_displays_current_vale_and_has_no_vale_selector` (leitura global), `test_other_tenant_cannot_read_or_edit_loja` e `test_loja_delete_is_blocked_while_members_are_linked`, além de `test_unselected_admin_can_open_store_form_and_create_for_selected_vale` e `test_unselected_admin_requires_active_vale_for_store_create`.
- [ ] **Step 4: Commit** — adiado; as mudanças estão no workspace sem commit para revisão do usuário (mesmo padrão dos planos 2026-10-16/17).

> **Ponto de decisão B-DP1 (spec de isolamento × WIP).** O WIP adiciona um seletor de Vale (`vales`/`vale_id`) para `admin_saas` em `loja_nova`. A spec manda o tenant ativo determinar o Vale (1 tenant = 1 Vale). Se o dono do plano quiser manter o seletor para `admin_saas` (ex.: operar em tenant "Todos"), isso **contradiz** a spec e exige nova decisão/atualização de spec antes de alterar o teste `test_loja_form_displays_current_vale_and_has_no_vale_selector`.

### Task B5: Verificar `test_vale_archive.py` e o restante do WIP

> **Execução 2026-10-18:** B5+C1 rodados juntos: `teste/test_vale_archive.py` +
> `teste/test_loja_pdf_local.py` → 10 passed, sem contratos divergentes. Também re-verificado o
> gate B/D3 ampliado: 104 passed com apenas os 2 legados do B-DP2.

**Files:**
- Test: `teste/test_vale_archive.py` (WIP, 113 linhas, sem falha conhecida)
- Test: `teste/test_loja_pdf_local.py` (fora do caso de PDF grande)

- [ ] **Step 1:** Rodar `python -m pytest teste/test_vale_archive.py teste/test_loja_pdf_local.py -q --no-header -o addopts='' --reuse-db -k "not oversized"` e confirmar que não há contrato divergente; se houver, tratar como B1–B4 (spec de isolamento/local-vale-contacts).
- [ ] **Step 2:** Commit apenas se houver mudança.

---

## Fase C — Teste de PDF grande executável no Windows

### Task C1: Eliminar o node id de 10 MB preservando a cobertura de tamanho

> **Execução 2026-10-18:** C1 aplicada exatamente como especificado (fábricas + `pytest.param(id=...)`)
> e módulo inteiro `teste/test_loja_pdf_local.py` verde incluindo `maior-que-10mb` no Windows
> (Sem `ValueError` de 32767). Ruff limpo.

**Files:**
- Modify: `teste/test_loja_pdf_local.py:102-122`
- Test: `teste/test_loja_pdf_local.py::test_upload_rejects_invalid_or_oversized_pdf`

**Interfaces:**
- Consumes: validação de produto já existente em `contatos/views/gprb_lojas.py` (`_MENSAGENS_ERRO['tamanho']`, limite 10 MB).
- Produces: os 3 casos (extensão inválida, assinatura inválida, >10 MB) rodando no Windows sem `ValueError: ... longer than 32767 characters`.

**Causa:** pytest 9 constrói o node id a partir do valor parametrizado; o caso `b'%PDF-' + b'x' * (10*1024*1024 + 1)` gera um id de ~10 MB, estourado o limite de 32767 caracteres da variável de ambiente `PYTEST_CURRENT_TEST` no Windows.

- [ ] **Step 1: RED** — `python -m pytest "teste/test_loja_pdf_local.py::test_upload_rejects_invalid_or_oversized_pdf" -q --no-header -o addopts='' --reuse-db`; Expected: ERROR de setup/teardown com `ValueError` do limite de 32767 (o caso `grande.pdf`), enquanto os dois casos pequenos passam.
- [ ] **Step 2: Trocar a parametrização por fábricas com `id` explícito**

```python
def _pdf_pequeno(): return b'%PDF-1.4\n'
def _pdf_assinatura_invalida(): return b'not a pdf'
def _pdf_grande(): return b'%PDF-' + b'x' * (10 * 1024 * 1024 + 1)

@pytest.mark.parametrize(
    ('factory', 'name', 'expected_error'),
    [
        pytest.param(_pdf_pequeno, 'valores.txt', 'invalido', id='extensao-invalida'),
        pytest.param(_pdf_assinatura_invalida, 'fake.pdf', 'invalido', id='assinatura-invalida'),
        pytest.param(_pdf_grande, 'grande.pdf', 'tamanho', id='maior-que-10mb'),
    ],
)
def test_upload_rejects_invalid_or_oversized_pdf(media_root, factory, name, expected_error):
    ...
    {'pdf': _pdf_upload(name, factory())},
    ...
```
(id via `pytest.param(..., id=...)`; não usar o bytes como valor do parâmetro.)

- [ ] **Step 3: GREEN** — `python -m pytest teste/test_loja_pdf_local.py -q --no-header -o addopts='' --reuse-db`; Expected: 3 casos + os demais testes do módulo passam; `PYTEST_CURRENT_TEST` curto.
- [ ] **Step 4: Commit** — `git add teste/test_loja_pdf_local.py`; `git commit -m "test: encurtar node id do teste de PDF grande no Windows"`.

---

## Fase D — Triage do inventário restante em gates incrementais

**Regra transversal:** antes de editar qualquer teste/produto, reproduzir o gate com `--create-db` num banco sem sobreposição (um só processo). Falhas por estado de banco (ex.: `test_vale_detalhe_isolation` com `IntegrityError` de FK `usuarios_tenant_id`) devem sumir — o Task 4 já mostrou o módulo passando sob `--create-db`. Não editar produto para mascarar contaminação.

### Task D0: Baseline controlada e atribuição

- [ ] **Step 1: Coleta limpa** — `python -m pytest teste/ --collect-only -q -o addopts=''`; Expected: 0 erros de coleta, **~768 itens** = ~724 (coleta que ainda tinha os 6 módulos com erro) + 44 (itens reabilitados pela Task 4). Aritmética: os 6 módulos desbloqueados somam 44 itens (relatório da Task 4: 36 passed / 6 failed / 2 errors = 44 coletados); logo ~724 + 44 = ~768.
- [ ] **Step 2: Gate total controlado (uma única execução, banco exclusivo)** — `python -m pytest teste/ -q --no-header -o addopts='' --create-db --continue-on-collection-errors`; comparar com 209/19 e marcar quais falhas eram contaminação.
- [ ] **Step 3: Exportar a lista de IDs** — salvar em `%TEMP%\opencode\` (fora do repo) e atribuir cada teste a um dos gates abaixo num arquivo de trabalho `DOCS/superpowers/plans/2026-10-12-residuais-triage.md` (versionar).

### Task D1: Gate de causas únicas (não-papel, não-WIP)

**Files (módulos):** `test_importador.py`(1), `test_cache_invalidation.py`(1), `test_lead_service.py`(1), `test_header_branding.py`(1), `test_mensalidade_labels.py`(1), `test_vale_labels.py`(1), `test_kanban_prefeitura.py`(1), `test_kanban_views.py`(2), `test_branding_emails.py`(4), `test_fase_s8_interface_seguranca.py`(5, inclui `test_allowed_hosts_falha_fechado_fora_do_debug`), `test_fase_s_candidatos.py`(1), `test_fase_t_oficialato.py`(4), `test_role_retirement*.py` (ver A3b).

- [ ] **Step 1: RED por módulo** — rodar cada um isolado com `--create-db`; confirmar a causa declarada no baseline (ex.: `test_branding_emails` = `'SALDA AMORIO'` vs `'SAL DA AMORIO'`; `allowed_hosts` = `DJANGO_SECRET_KEY` ausente em produção). Checar contra spec de origem (`2026-10-10-amorio-*`) antes de decidir teste vs produto.
- [ ] **Step 2: Corrigir o lado errado** — por módulo, editar só a expectativa (se stale) ou o produto (se spec confirma), sem misturar.
- [ ] **Step 3: GREEN** — repetir o módulo; Expected: 0 falhas.
- [ ] **Step 4: Commit** — um commit por módulo: `git commit -m "test/docs/fix: <modulo> alinhado ao contrato atual"`.

### Task D2: Gate de papéis/semântica (Fase A)

**Files (módulos):** `test_rbac_api.py`(6), `test_rbac_web.py`(1), `test_equipe.py`(8), `test_fase_b_config.py`(1), `test_fase_k_timestamps.py`(2), `test_viewer.py`(3+1), `test_contatos_api.py`(13), `test_atividades_view.py`(11), `test_dashboard_avancado.py`(7), `test_comunicacao.py`(4), `test_campos_personalizados.py`(7), `test_cache_invalidation.py`(1) e demais módulos com `usuario_operacional`/`admin_company` (Fase A).

- [ ] **Step 1: GREEN do gate** — `python -m pytest <módulos> -q --no-header -o addopts='' --reuse-db`; comparar com o cenário pré-Fase A para medir a queda.
- [ ] **Step 2: Triar o restante** — o que sobrar é produto (ex.: `test_contatos_api` retorna 403 para usuário de tenant porque a API exige outro perfil) → verificar contra a spec/PRD da API antes de tocar produto; registrar decisão.
- [ ] **Step 3: Commit** — `git commit -m "test: fechar gate de papeis/semantica"`.

### Task D3: Gate de contratos WIP (Fase B/C)

- [ ] **Step 1: GREEN do gate** — `python -m pytest teste/test_loja_local.py teste/test_membro_local.py teste/test_loja_pdf_local.py teste/test_vale_templates.py teste/test_vale_archive.py teste/test_potencia_web.py teste/test_vale_detalhe_isolation.py -q --no-header -o addopts='' --create-db`; Expected: 44 coletados e **0 falhas** (hoje: 36 passed / 6 failed / 2 errors).
- [ ] **Step 2: Commit** — se houver ajustes não commitados, `git commit -m "test: fechar gate de contratos WIP de Vale/Loja"`.

### Task D4: Gate das suítes de feature restantes

**Files (módulos):** `test_fase_a_funil.py`(9), `test_fase_f_pipeline.py`(10), `test_fase_g_tarefas.py`(7), `test_fase_i_automacoes.py`(18), `test_fase_j_lead_orcamento_metas.py`(10), `test_fase_n_carteiras.py`(16), `test_fase_o_email_avancado.py`(6), `test_fase_r_lead_rapido.py`(13), `test_leads_view.py`(7), `test_import_view.py`(8), `test_saas_tenant_write_scope.py`(3), `test_vale_provisioning.py`(3), `test_ranking_presenca.py`(11 errors).

- [ ] **Step 1: RED/reprodução por submódulo** — rodar por arquivo com `--create-db` e classificar cada falha: (papel | produto | WIP | estado do banco).
- [ ] **Step 2: Corrigir em lotes pequenos** — quando a causa for papel, reutilizar A1/A4; quando for produto/API (ex.: `test_fase_i` web `403`/`'SALDA AMORIO'`, `test_ranking_presenca` `contatos...`), abrir decisão contra o spec do módulo antes de alterar produto.
- [ ] **Step 3: GREEN por arquivo + commit por lote** — `git commit -m "test: fechar gate <arquivo>"`.

### Task D5: Verificação final (sem rodar a suíte inteira desnecessariamente)

- [ ] **Step 1** — `python manage.py check`; Expected: `System check identified no issues`.
- [ ] **Step 2** — `python manage.py makemigrations --check --dry-run`; Expected: `No changes detected`.
- [ ] **Step 3** — rodar a suíte completa **uma vez** só quando os gates D1–D4 estiverem verdes, para o número final.

---

## Fora deste plano

- **Residuais observados em 2026-10-18:** `teste/test_evento_vale_loja.py` — 5 falhas: o produto
  (`tarefas/views.py`) passou a exigir `tipo='iniciacao_grau_*'` para todo evento e os testes
  POSTam eventos sem `tipo` (400 `Todo evento deve estar associado a um grau da Loja.`).
  Atualizar os payloads do teste ou relaxar a validação — decisão contra o spec
  `2026-10-12-agenda-eventos-presenca-lembretes`. `makemigrations --check` ainda reporta
  `Alter field id on emaileventofila` (drift do WIP de agenda).
- Execução das Tasks 2–6 do plano de aposentadoria de papéis (`2026-10-08-retire-tenant-roles-and-saas-admin.md`) — A-DP1 apenas decide se elas entram como pré-requisito.
- Correção de produto dos `test_role_retirement*` (migração 0019 / refresh de sessão) — encaminhar ao projeto de aposentadoria; este plano só os cataloga.
- Alinhamento de credenciais `gprb` do Docker (`::1`) × Postgres nativo (`127.0.0.1`) — registrado no spec.
- Achados de revisão de código (N+1, imports inline, `membros_total == membros_ativos`, `ROLE_ADMIN_COMPANY` em produção além do necessário para A-DP1).

## Self-Review

- **Cobertura do brief:** (a) Fase A; (b) Fase B; (c) Fase C; (d) Fase D com gates; restrição de não mexer produto sem spec — A-DP1 + cada "Passo 2" da Fase B/C/D checam spec antes de editar. ✔
- **Dependências:** A1 → A2/A3/A4; A-DP1 bloqueia A3/A4; D0 → D1..D4; B/C alimentam D3. ✔
- **Dados concretos:** totais 454/209/48/19 (6+13), 36/6/2 do Task 4; módulos e contagens por arquivo; IDs de teste citados; links para baseline/task-4/t2_full_run/t2_failed_lines. ✔
- **Segurança de escopo:** não editar `test_role_retirement*`; não commitar senha (placeholder `$env:VALE_TEST_DATABASE_URL='...'`); não `git add -A`; isolamento preservado em cada task. ✔
- **Consistência de tipos:** fixtures `usuario_viewer`/`usuario_editor`/`admin_saas_tenant`; chaves de contexto `secretario_*`/`tesoureiro_*`; `resolve_tenant_id`/`admin_tenant_id` batem com `acesso/tenant_context.py`. ✔
