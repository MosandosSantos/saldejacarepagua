# Desbloquear a suíte de testes (migrations, rótulos e papéis aposentados) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer `python manage.py migrate` (do zero) funcionar no Django 6.0.8 e `pytest` coletar/rodar com a configuração padrão, corrigindo migrations com referências minúsculas, rótulos de template desatualizados e imports de papéis renomeados nos testes.

**Architecture:** Três frentes independentes, nesta ordem de dependência: (A) migrations — destrava a criação do banco de teste; (B) papéis renomeados nos testes — destrava a coleta; (C) rótulos de template — corrige asserções obsoletas. Cada frente é um conjunto de edições pontuais validadas por execução real da suíte.

**Tech Stack:** Django 6.0.8, pytest + pytest-django, PostgreSQL (nativo `127.0.0.1:5432`, banco `gprbr_test`).

**Spec:** `DOCS/superpowers/specs/2026-10-12-suite-teste-bloqueios-pre-existentes-design.md`

## Global Constraints

- Django `6.0.8` (referências de modelo em migrations devem ser **case-exact**: `contatos.Loja`, `contatos.LojaCargo`).
- Papéis atuais (`acesso/models.py`): `ROLE_ADMIN_SAAS='admin_saas'`, `ROLE_VIEWER='viewer'`, `ROLE_ADM='ADM'`, `ROLE_TESOUREIRO`, `ROLE_SECRETARIO`, `ROLE_DELEGADO='delegado'`, `ROLE_PRESIDENTE_CORPO`. Removidos: `ROLE_GRANDE_PRIOR`, `ROLE_ADMIN_COMPANY='admin_company'`, `ROLE_OPERACIONAL='operacional'`.
- `ROLE_ADM` é tratado como admin global em `contatos/views/vales.py::_vales_do_request` (vê todos os Vales ativos); papéis de oficialato/tenant (`ROLE_DELEGADO` etc.) são escopados por tenant.
- Semântica de gerir Vale: `_pode_gerir_vale` = `ROLE_ADMIN_SAAS` ou `ROLE_ADM`; `_pode_alterar_vale` inclui `ROLE_DELEGADO`.
- Comando de teste (PowerShell), executado na raiz do repo:
  ```powershell
  $env:VALE_TEST_DATABASE_URL='postgresql://postgres:KXIr%25TG!AU*7(7UK%3C(%25Nhzr0KT%24osb@127.0.0.1:5432/gprbr_test'
  ```
- Não alterar o comportamento de produto; apenas migrations (string de referência), testes e rótulos de teste.
- Não editar `teste/test_role_retirement*.py` (usam as strings legadas de propósito para validar a migração de papéis).

## Review Focus

- **Migração em banco já migrado:** editar um arquivo de migration já aplicado (`agenda/0001_initial.py`) não pode reexecutá-lo nem alterar o schema existente (Django não guarda checksum aplicado). O teste de Task 1 deve cobrir `migrate` do zero **e** um segundo `migrate` idempotente.
- **Drift de modelo:** as migrations locais devem continuar batendo com os models — `makemigrations --check` deve retornar "No changes detected" após as edições.
- **Escopo de papel:** trocar um papel por outro não pode afroupar isolamento de tenant. Testes que trocam `ROLE_GRANDE_PRIOR`→`ROLE_DELEGADO` não podem passar a ver dados de outro tenant.
- **`--reuse-db` com banco defasado:** o banco `test_saldabritanea_vales` já existe só com `contatos.0001`; a primeira execução após Task 1 precisa recriá-lo (`--create-db`) e depois rodar com a config padrão.
- **Coleta vs. falha:** depois de Task 1, todo módulo de `teste/test_*.py` deve ser coletado (nenhum `ImportError`); falhas restantes são tratadas por Tasks 3–5.

---

### Task 1: Corrigir referências de modelo minúsculas nas migrations (A)

**Files:**
- Modify: `contatos/migrations/0017_loja_membro_locais.py:48,93`
- Modify: `contatos/migrations/0018_loja_pdf_required.py:19`
- Modify: `contatos/migrations/0023_filiacao_lojacargo_historicocargo_and_more.py:23,40,55,58,68`
- Modify: `agenda/migrations/0001_initial.py:61`

**Interfaces:**
- Produces: migrations aplicáveis do zero → habilita a criação do banco de teste em todas as tasks.

- [ ] **Step 1: Estabelecer a falha (RED)**

Run:
```powershell
$env:VALE_TEST_DATABASE_URL='postgresql://postgres:KXIr%25TG!AU*7(7UK%3C(%25Nhzr0KT%24osb@127.0.0.1:5432/gprbr_test'
python -m pytest teste/test_vale_provisioning.py -q --no-header -o addopts='' --create-db
```
Expected: FAIL/ERROR com `ValueError: Related model 'contatos.loja' cannot be resolved` (aplicando `contatos.0017`/`agenda.0001`).

- [ ] **Step 2: Capitalizar `contatos.loja` e `contatos.lojacargo`**

Em cada ocorrência listada nos 4 arquivos, trocar a string:
- `to='contatos.loja'` → `to='contatos.Loja'`
- `to='contatos.lojacargo'` → `to='contatos.LojaCargo'`

(Nenhuma outra alteração nos arquivos.)

- [ ] **Step 3: Verificar ausência de drift**

Run: `python manage.py makemigrations --check --dry-run`
Expected: `No changes detected`.

- [ ] **Step 4: Verificar `migrate` do zero e idempotência**

Run:
```powershell
$env:VALE_TEST_DATABASE_URL='postgresql://postgres:KXIr%25TG!AU*7(7UK%3C(%25Nhzr0KT%24osb@127.0.0.1:5432/gprbr_test'
python -m pytest teste/test_vale_provisioning.py -q --no-header -o addopts='' --create-db
```
Expected: `9 passed` (verde).

- [ ] **Step 5: Commit**

```bash
git add contatos/migrations/0017_loja_membro_locais.py contatos/migrations/0018_loja_pdf_required.py contatos/migrations/0023_filiacao_lojacargo_historicocargo_and_more.py agenda/migrations/0001_initial.py
git commit -m "fix(migrations): corrigir referencias de modelo em minusculas (Django 6)"
```

---

### Task 2: Baseline da suíte com a configuração padrão

**Files:**
- Create: `DOCS/superpowers/plans/2026-10-12-suite-teste-baseline.txt` (inventário)

**Interfaces:**
- Consumes: Task 1 (migrate funcional).
- Produces: lista de módulos que não coletam e de testes que falham → direciona Tasks 3–5.

- [ ] **Step 1: Recriar o banco de teste e rodar a suíte inteira**

Run:
```powershell
$env:VALE_TEST_DATABASE_URL='postgresql://postgres:KXIr%25TG!AU*7(7UK%3C(%25Nhzr0KT%24osb@127.0.0.1:5432/gprbr_test'
python -m pytest teste/ -q --no-header -o addopts='' --create-db 2>&1 | Tee-Object -FilePath DOCS/superpowers/plans/2026-10-12-suite-teste-baseline.txt
```
Expected: erros de coleta (`ImportError: ROLE_GRANDE_PRIOR`) e falhas listadas ao final.

- [ ] **Step 2: Catalogar o resultado**

No arquivo criado, anotar em `## Resumo` (anexado ao fim do arquivo): contagem de `passed`, `failed`, `errors`, e a lista de módulos com `ERROR collecting`. Esta lista alimenta as Tasks 3–5.

- [ ] **Step 3: Rodar a config padrão (com `--reuse-db`) para confirmar que o comando default funciona**

Run: `python -m pytest teste/ -q --no-header 2>&1 | Select-Object -Last 20`
Expected: a suíte **executa** (mesmo com falhas) sem erro de banco/migration.

- [ ] **Step 4: Documentar o pré-requisito de infra**

Anexar ao arquivo `## Infra` com: alvo `VALE_TEST_DATABASE_URL=...gprbr_test` (Postgres nativo `127.0.0.1`), comando de recriação (`--create-db`) e a nota de que `--reuse-db` (pytest.ini) só funciona após o banco estar atualizado.

- [ ] **Step 5: Commit**

```bash
git add DOCS/superpowers/plans/2026-10-12-suite-teste-baseline.txt
git commit -m "docs(test): registrar baseline da suite de testes"
```

---

### Task 3: Atualizar rótulos de template desatualizados nos testes (C)

**Files:**
- Modify: `teste/test_vale_labels.py:58`
- Modify: `teste/test_kanban_prefeitura.py:152`

**Interfaces:**
- Consumes: baseline de Task 2.
- Produces: as duas falhas de rótulo eliminadas.

- [ ] **Step 1: Estabelecer a falha (RED)**

Run:
```powershell
$env:VALE_TEST_DATABASE_URL='postgresql://postgres:KXIr%25TG!AU*7(7UK%3C(%25Nhzr0KT%24osb@127.0.0.1:5432/gprbr_test'
python -m pytest teste/test_vale_labels.py::test_prefeitura_entity_no_longer_uses_potencia_in_templates "teste/test_kanban_prefeitura.py::test_kanban_view_select_prefeitura_inclui_opcoes" -q --no-header -o addopts='' --create-db
```
Expected: 2 failed (esperam `Excluir Vale` e `Todas as Prefeituras`).

- [ ] **Step 2: Corrigir as expectativas**

- Em `teste/test_vale_labels.py`, na tupla de rótulos, trocar `('prefeitura_excluir.html', 'Excluir Vale')` por `('prefeitura_excluir.html', 'Arquivar Vale')`.
- Em `teste/test_kanban_prefeitura.py:152`, trocar `assert b'Todas as Prefeituras' in response.content` por `assert b'Todos os vales' in response.content`.

- [ ] **Step 3: Verificar verde**

Run:
```powershell
python -m pytest teste/test_vale_labels.py "teste/test_kanban_prefeitura.py" -q --no-header -o addopts='' --reuse-db
```
Expected: PASS nas duas asserções corrigidas (a falha de `test_kanban_views` não pertence a esta task).

- [ ] **Step 4: Commit**

```bash
git add teste/test_vale_labels.py teste/test_kanban_prefeitura.py
git commit -m "test: atualizar rotulos de template (Arquivar Vale / Todos os vales)"
```

---

### Task 4: Substituir `ROLE_GRANDE_PRIOR` (renomeado para `ROLE_ADM`) nos testes (B1)

**Files:**
- Modify: `teste/test_loja_local.py:9,37`
- Modify: `teste/test_membro_local.py:10,35`
- Modify: `teste/test_loja_pdf_local.py:10,49`
- Modify: `teste/test_vale_templates.py:9,19`
- Modify: `teste/test_vale_archive.py:9,57,73`
- Modify: `teste/test_potencia_web.py:11,35,211-231`

**Interfaces:**
- Consumes: `ROLE_DELEGADO` (editor de tenant) e `ROLE_ADM` (gere/gere global) de `acesso.models`.
- Produces: os 6 módulos voltam a coletar.

- [ ] **Step 1: Estabelecer a falha (RED)**

Run:
```powershell
$env:VALE_TEST_DATABASE_URL='postgresql://postgres:KXIr%25TG!AU*7(7UK%3C(%25Nhzr0KT%24osb@127.0.0.1:5432/gprbr_test'
python -m pytest teste/test_loja_local.py teste/test_membro_local.py teste/test_loja_pdf_local.py teste/test_vale_templates.py teste/test_vale_archive.py teste/test_potencia_web.py -q --no-header -o addopts='' --create-db
```
Expected: ERROR de coleta `ImportError: cannot import name 'ROLE_GRANDE_PRIOR'`.

- [ ] **Step 2: `test_loja_local.py`, `test_membro_local.py`, `test_loja_pdf_local.py`, `test_vale_templates.py` — papel de editor de tenant**

Trocar o import e os usos:
- Import: `ROLE_GRANDE_PRIOR` → `ROLE_DELEGADO` (mantendo os demais símbolos do import).
- `test_loja_local.py:37` / `test_membro_local.py:35`: `role=ROLE_GRANDE_PRIOR` → `role=ROLE_DELEGADO`.
- `test_loja_pdf_local.py:49`: `role=ROLE_GRANDE_PRIOR` → `role=ROLE_DELEGADO`.
- `test_vale_templates.py:19`: `role=ROLE_GRANDE_PRIOR` → `role=ROLE_DELEGADO`.

- [ ] **Step 3: `test_vale_archive.py` — papel do usuário-do-tenant**

Import: `ROLE_GRANDE_PRIOR` → `ROLE_DELEGADO`. Em `:57` e `:73`, `ROLE_GRANDE_PRIOR` → `ROLE_DELEGADO` (o arquivamento é feito por `admin_saas`; o papel aqui só representa um usuário existente do tenant).

- [ ] **Step 4: `test_potencia_web.py` — editor de tenant + papel que gere**

Import: `ROLE_GRANDE_PRIOR` → `ROLE_DELEGADO`, e adicionar `ROLE_ADM` ao import.
- `:35` default `_usuario(tenant, role=ROLE_DELEGADO)`.
- `test_archive_vale_preserves_local_record_and_tenant` (`:211-231`): o cliente que arquiva precisa de `_pode_gerir_vale`; trocar `_cliente(_usuario(tenant))` por `_cliente(_usuario(tenant, ROLE_ADM))`.
- Manter as asserções de isolamento (`test_list_vales_is_tenant_scoped` deve continuar vendo só o próprio tenant — `ROLE_DELEGADO` é escopado).

- [ ] **Step 5: Verificar (GREEN)**

Run:
```powershell
$env:VALE_TEST_DATABASE_URL='postgresql://postgres:KXIr%25TG!AU*7(7UK%3C(%25Nhzr0KT%24osb@127.0.0.1:5432/gprbr_test'
python -m pytest teste/test_loja_local.py teste/test_membro_local.py teste/test_loja_pdf_local.py teste/test_vale_templates.py teste/test_vale_archive.py teste/test_potencia_web.py teste/test_vale_detalhe_isolation.py -q --no-header -o addopts='' --create-db
```
Expected: todos os 6 módulos coletam; os testes de papel/isolamento passam. Se o run completo expuser falhas de funcionalidade preexistentes no WIP, registrá-las no report e não alterar produto nem enfraquecer as assertions sem spec. Ajustes de papel permitidos: editor escopado = `ROLE_DELEGADO`; gerir/global = `ROLE_ADM` — nunca afrouxar a asserção de isolamento.

- [ ] **Step 6: Commit**

```bash
git add teste/test_loja_local.py teste/test_membro_local.py teste/test_loja_pdf_local.py teste/test_vale_templates.py teste/test_vale_archive.py teste/test_potencia_web.py
git commit -m "test: substituir ROLE_GRANDE_PRIOR por papeis atuais"
```

---

### Task 5: Planejar os bloqueios residuais da suíte (B2 + mismatches do WIP)

**Files:**
- Create: `DOCS/superpowers/plans/2026-10-12-suite-teste-residuais.md` (plano dedicado)

**Interfaces:**
- Consumes: baseline de Task 2 (lista de falhas restantes).
- Produces: plano dedicado para o débito de papéis legados e demais falhas de suíte observadas; **não implementa** aqui.

**Contexto:** além dos imports, há uso das strings/papéis aposentados em testes legados que exigem decisão semântica (não é rename mecânico): `teste/conftest.py` (fixtures `usuario_operacional`, `admin_company`, `headers_*`), `teste/test_auth_api.py`, `teste/test_ativacao_web.py`, `teste/test_equipe.py`, `teste/test_fase_b_config.py`, `teste/test_fase_j_lead_orcamento_metas.py`, `teste/test_fase_k_timestamps.py`, `teste/test_rbac_api.py`. As funções de `admin_company` foram transferidas para `admin_saas` com tenant selecionado (`admin_tenant_id`); `operacional` virou `viewer`. Também incorporar as falhas fora de B1 do baseline (209 falhas / 19 erros no run complementar) e as 6 falhas + 2 erros descobertos ao liberar coleta em Task 4: mismatchs entre testes WIP e contratos de Loja/tenant/admin/templates e limite de ID de parametrização de PDF no Windows. Não corrigir esses contratos sem consultar specs/designs que os originaram.

- [ ] **Step 1: Extrair do baseline e do relatório Task 4 todas as falhas ainda abertas**

Run: revisar `DOCS/superpowers/plans/2026-10-12-suite-teste-baseline.txt` e `.superpowers/sdd/2026-10-12-suite-teste-bloqueios-pre-existentes/task-4-report.md`; catalogar os bloqueios de coleta, falhas por papel, mismatches de comportamento/template e o erro do node id PDF.

- [ ] **Step 2: Escrever um plano dedicado** (`DOCS/superpowers/plans/2026-10-12-suite-teste-residuais.md`) usando a skill `writing-plans`, com escopo/fases separados: (a) `admin_company` → `admin_saas` + `admin_tenant_id`; `operacional` → `viewer` ou oficialato conforme a asserção; (b) falhas WIP de Loja/Vale/templates, resolvendo contra os specs que originaram os testes sem enfraquecer isolamento; (c) fazer o teste PDF executável no Windows sem node id gigante; (d) priorizar o inventário restante da suíte e definir gates incrementais. O plano deve manter a restrição de não alterar comportamento do produto sem autorização/spec.

- [ ] **Step 3: Commit**

```bash
git add DOCS/superpowers/plans/2026-10-12-suite-teste-residuais.md
git commit -m "docs(plans): planejar os bloqueios residuais da suite"
```

---

## Fora deste plano

- Correção dos bloqueios residuais funcionais/legados depois do plano de Task 5 (depende de decisões semânticas e sobrepõe o projeto de aposentadoria de papéis em `DOCS/superpowers/plans/2026-10-08-retire-tenant-roles-and-saas-admin.md`).
- Alinhamento de credenciais `gprbr` do Docker (`::1`) × Postgres nativo (`127.0.0.1`) — registrado no spec.
- Achados da revisão de código (N+1, imports inline, `membros_total == membros_ativos`, `ROLE_ADMIN_COMPANY` em produção).

## Self-Review (feito ao escrever)

- **Cobertura do spec:** A → Task 1; C → Task 3; B → Tasks 4 (import) e 5 (débito legado); infra → Task 2. ✔
- **Granularidade:** cada task tem passo RED, edição, GREEN e commit. ✔
- **Consistência:** `ROLE_DELEGADO`/`ROLE_ADM` batem com `acesso/models.py`; nomes de arquivos/linhas conferidos por grep. ✔
- **Review Focus:** coberto por Task 1 (migrate do zero/idempotência + `makemigrations --check`) e Task 4 (isolamento preservado). ✔
