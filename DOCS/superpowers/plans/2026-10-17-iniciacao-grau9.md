# Iniciação ao Grau 9 — Plano de Implementação

> **Para execução autônoma neste workspace:** REQUIRED SUB-SKILL: `executing-plans`; o usuário pediu execução nativa, sem subagentes, com revisão posterior. TDD em cada tarefa. Não criar commits.

**Objetivo:** adicionar uma página somente de consulta que liste candidatos ativos ao Grau 9 conforme histórico de graus e presença no Vale.

**Arquitetura:** uma função de domínio calcula candidatos a partir de `Membro`, `GrauMembro`, `Loja`, `Evento` e `PresencaEvento`; uma view autenticada usa o mesmo escopo de tenant do Acompanhamento; um template HAZON mostra somente a lista do Grau 9. A candidatura é derivada e não persistida.

**Tech Stack:** Django 5.2, Python 3.13, PostgreSQL, templates Django/Tailwind HAZON, pytest-django e `python-dateutil` já existente.

**Spec:** `specs/011-iniciacao-grau9/spec.md`

## Global Constraints

- Primeira entrega: somente candidatos ao Grau 9; outras regras ficam para extensões futuras.
- Maior grau histórico exatamente 8; Grau 4 estritamente anterior à data local atual menos seis meses de calendário.
- Presença = presentes / todas as chamadas registradas em Lojas locais do mesmo tenant, sem janela temporal; sem registros não qualifica; 50% exatos qualificam.
- A lista contém somente membros ativos e é calculada dinamicamente; nenhum estado de candidatura é gravado.
- Respeitar tenant no servidor; não confiar em parâmetros do cliente.
- Não mudar modelos/schema, não adicionar dependências, não alterar `/iniciacao/` comercial, Acompanhamento ou relatórios.
- Regras dos Graus 14–33 descritas na spec são futuras, não fazem parte do código da Fase 1.

## Review Focus

- Grau atual acima de 8 ou diferente de 8 não pode qualificar; o maior grau é tenant-scoped.
- Exatamente seis meses desde o Grau 4 não basta; mais de seis meses basta.
- 49.99% e nenhuma chamada não qualificam; 50% exatos qualificam.
- Uma chamada de outra Loja do mesmo Vale conta; chamada de outra tenant não conta mesmo com relação inconsistente.
- Usuário de tenant A nunca recebe membro, grau ou presença do tenant B.

---

## Mapa de arquivos

- `contatos/iniciacao_graus.py` (novo): regra de elegibilidade e objeto candidato.
- `contatos/views/iniciacao_graus.py` (novo): autenticação, tenant scope e contexto.
- `contatos/membros_urls.py`, `contatos/views/__init__.py`: rota e export da view.
- `contatos/templates/contatos/iniciacao_graus.html` (novo): lista e estado vazio.
- `acesso/context_processors.py`: navegação independente e matcher de rota ativo.
- `teste/test_iniciacao_graus.py` (novo): testes do serviço, view, página e tenant.

## Interfaces

- Signature exata: `@dataclass(frozen=True) CandidatoGrau9(membro: Membro, vale_nome: str, data_grau_4: date, presenca_percentual: float)`; `candidatos_grau_9(tenant_ids: list[int] | None, hoje: date | None = None) -> list[CandidatoGrau9]`.
- Task 1 produz `CandidatoGrau9(membro, data_grau_4, presenca_percentual)` e `candidatos_grau_9(tenant_ids, hoje=None) -> list[CandidatoGrau9]`.
- Task 2 consome `candidatos_grau_9` e produz o contexto `candidatos` para o template.
- Task 3 consome `candidatos` e expõe `membros:iniciacao`; o item de navegação usa matcher apenas para `iniciacao`.
- Task 4 não altera a API; verifica o resultado integrado.

### Task 1: Serviço de elegibilidade

**Files:** criar `contatos/iniciacao_graus.py`; criar `teste/test_iniciacao_graus.py`.

**Testes:** `test_candidato_grau9_qualifica_com_grau8_data_e_presenca`, `test_grau9_requer_maior_grau_exatamente_8`, `test_grau9_requer_grau4_mais_antigo_que_seis_meses`, `test_grau9_requer_chamadas_e_presenca_minima`, `test_grau9_agrega_lojas_do_vale_sem_vazar_tenant`.

- [x] **Step 1: Escrever RED** com `test_pagina_iniciacao_mostra_candidato_grau9_com_dados_de_elegibilidade`, verificando a rota, nome, data do Grau 4 e presença para um membro elegível com chamadas em duas Lojas do Vale.
- [x] **Step 2: Executar RED** — `pytest` deve receber HTTP 500/404 em `/membros/iniciacao/` porque a nova rota ainda não existe (o path cai na rota dinâmica de detalhe do membro).
- [x] **Step 3: Implementar** `CandidatoGrau9` e `candidatos_grau_9(tenant_ids: list[int] | None, hoje: date | None = None) -> list[CandidatoGrau9]`; usar `timezone.localdate`, `relativedelta(months=6)`, comparação estrita para Grau 4, maior grau exatamente 8 e presença exata ≥50.
- [x] **Step 4: Agregar presença sem N+1**, por membro e somente para IDs de Loja local do tenant; `True` é numerador e todos os registros de chamada são denominador. A função recebe IDs autorizados ou `None` para o escopo global já autorizado.
- [x] **Step 5: Rodar** `python -m pytest teste/test_iniciacao_graus.py -k 'grau9 and not pagina' --ds=core.settings_vale_test --reuse-db -q`; esperado: casos de regra e tenant passam.

### Task 2: View e rota autenticada

**Files:** criar `contatos/views/iniciacao_graus.py` e `contatos/templates/contatos/iniciacao_graus.html`; modificar `contatos/membros_urls.py`, `contatos/views/__init__.py`; estender `teste/test_iniciacao_graus.py`.

- [x] **Step 1: Escrever testes RED** para reverse da rota, login, Vale ativo, tenant comum e isolamento entre tenants.
- [x] **Step 2: Rodar os testes**; esperado: URL/view/contexto não existem.
- [x] **Step 3: Implementar** view `iniciacao_graus(request)` com `web_login_required`, `_tem_vale_ativo(request)`, `_tenant_ids_para_lista(request)` e chamada ao serviço; não aceitar tenant na query string.
- [x] **Step 4: Registrar** `path('iniciacao/', views.iniciacao_graus, name='iniciacao')` antes da rota dinâmica `<str:pk>/` e expor a função em `views.__init__`.
- [x] **Step 5: Criar a página HAZON final** com um ledger Grau 9 e colunas Vale, Membro, Grau 4 desde e Presença no Vale; incluir estado vazio e comentário curto de direção de interface.
- [x] **Step 6: Rodar** os testes focados; esperado: acesso, conteúdo e tenant scope corretos.

### Task 3: Página e navegação

**Files:** modificar `acesso/context_processors.py`; estender `teste/test_iniciacao_graus.py`.

- [x] **Step 1: Escrever teste RED** para item de navegação ativo somente na nova rota e Acompanhamento inativo em `membros:iniciacao`.
- [x] **Step 2: Rodar o teste**; esperado: a navegação ainda marca o item Acompanhamento para todo o namespace `membros`.
- [x] **Step 3: Adicionar** menu `Iniciação a Graus` junto ao Acompanhamento e restringir o matcher de Acompanhamento aos próprios URL names.
- [x] **Step 4: Rodar** teste de navegação e detector Impeccable no novo template; corrigir somente achados mecânicos desta página.

### Task 4: Verificação local e handoff

**Files:** apenas correções necessárias nos arquivos anteriores.

- [x] Rodar os testes focados do novo fluxo e Ruff dos arquivos alterados.
- [x] Rodar `manage.py check` e `makemigrations --check --dry-run`; nenhuma migration deve surgir.
- [x] Rebuild local com `docker compose up -d --build app`; confirmar `/healthz/` HTTP 200 e rota carregável.
- [x] Rodar a suíte completa uma vez após as mudanças; registrar o resultado (`211 failed, 663 passed, 48 skipped, 37 errors`) e confirmar que os módulos de teste desta feature não aparecem entre falhas/erros.
- [x] Não fazer commit/push/deploy; deixar spec, plano e alterações no workspace para revisão do usuário.
