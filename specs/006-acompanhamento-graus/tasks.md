# Acompanhamento de Membros e Histórico de Graus — Plano de Implementação

> **Status:** o usuário aprovou a implementação. Tarefas seguem TDD; não fazer merge/deploy enquanto o gate de suite completa estiver vermelho.

**Objetivo:** Adicionar acompanhamento de membros com datas dos graus 4º–33º, filtros, ordenação e presença, substituindo no menu o link Financeiro sem remover o módulo.

**Arquitetura:** Usar `GrauMembro` como tabela normalizada de histórico; editar seus registros por formset transacional; servir uma página separada e tenant-scoped com 30 colunas de data. A presença vem de `PresencaServico`; a navegação muda apenas seu link.

**Stack:** Django `>=5.2,<5.3` (requisito declarado), Python 3.13, PostgreSQL, pytest/pytest-django, Ruff, GitHub Actions.

**Spec:** `specs/006-acompanhamento-graus/spec.md`

## Restrições globais

- Cada linha de `GrauMembro` tem um membro, um grau 4–33 e uma data obrigatória de obtenção.
- Não permitir datas futuras nem duplicar grau no mesmo membro.
- Não salvar parcialmente formsets inválidos.
- Preservar tenant scope do membro; não confiar em tenant enviado por query/form.
- Remover somente `Membro.data_iniciacao`, `Membro.data_passagem` e `Membro.data_elevacao`.
- Preservar `HistoricoCargo.data_passagem` e todas as rotas/views financeiras.
- Não executar limpeza de dados via migration, startup ou CI.
- Todo comportamento novo começa com teste falhando; alterações de configuração/migration também recebem teste/validação antes da implementação quando aplicável.

## Arquivos e responsabilidades previstas

| Arquivo | Responsabilidade |
|---|---|
| `contatos/forms_graus.py` | Form/model formset de grau e data, validação e escopo do membro |
| `contatos/views/gprb_membros.py` | Processar o formset dentro da edição existente |
| `contatos/views/acompanhamento.py` | Consultar, filtrar, ordenar, paginar e serializar dados |
| `contatos/templates/contatos/acompanhamento.html` | Filtros e tabela de 30 graus |
| `contatos/models.py` + migration nova | Remover três datas antigas de Membro; restringir catálogo a 4–33 |
| `contatos/management/commands/limpar_historico_graus_teste.py` | Dry-run por padrão; apagar somente com `--confirm` |
| `contatos/membros_urls.py`, `contatos/views/__init__.py` | Registrar rota e export da view |
| `acesso/context_processors.py` | Link de menu Acompanhamento no lugar de Financeiro |
| `.github/workflows/ci.yml` | Corrigir indentação/sintaxe e validar gates |
| `Dockerfile`, `.dockerignore`, `entrypoint.sh` | Build/collectstatic do CSS Tailwind para contêineres novos |
| `teste/test_acompanhamento_graus.py` | Testes novos de formulário, página, filtros, tenant, presença e queries |
| `teste/test_membro_grau_web.py`, `teste/test_membro_local.py`, `teste/test_membro_web.py` | Atualizar regressões de interface/campos de membro removidos |

## Review Focus

1. Usuário forja ID de grau, membro, Loja ou Vale pertencente a outro tenant — teste de formset/página comprova bloqueio/escopo.
2. POST com uma data inválida entre várias linhas — teste comprova rollback integral.
3. Vários graus selecionados — teste comprova semântica OR, sem duplicar membro.
4. Presença exatamente 50% ou ausente — teste comprova que nome não fica vermelho.
5. 25 membros com múltiplos graus e Lojas — teste comprova 30 células por linha e ausência de query N+1.

---

### Tarefa 1: Remover datas antigas do schema de Membro

**Arquivos:** `contatos/models.py`, migration nova em `contatos/migrations/`, `contatos/views/gprb_membros.py`, novo `teste/test_acompanhamento_graus.py`.

**Interface:** retirar do modelo apenas `Membro.data_iniciacao`, `Membro.data_passagem` e `Membro.data_elevacao`. Deixar `HistoricoCargo.data_passagem` intacto.

- [x] **Passo 1 — Escrever os testes falhando:** criados `test_membro_table_does_not_keep_legacy_ritual_date_columns` e `test_historico_cargo_keeps_data_passagem_column` usando introspecção real do PostgreSQL.
- [x] **Passo 2 — Verificar RED:** a asserção da tabela `membros` falhou pelas três colunas antigas; `historicos_cargos.data_passagem` passou.
- [x] **Passo 3 — Implementar mínimo:** removidos somente os três campos de `Membro`, removidos de `_CAMPOS_DATA` para que POST legado não passe kwargs inválidos e criada migration `0024_remove_membro_data_elevacao_and_more.py`; campos homônimos e mapeamento GPRB não alterados.
- [x] **Passo 4 — Verificar GREEN:** os dois testes de schema passaram e `makemigrations --check --dry-run` não detectou drift.
- [x] **Passo 5 — Regressão:** `15 passed, 9 skipped` nos testes de schema e regressão de membros.

### Tarefa 2: Remover inputs e referências antigas da interface local

**Arquivos:** `contatos/templates/contatos/membro_editar.html`, `contatos/templates/contatos/membro_detalhe.html`, `teste/test_membro_local.py`, `teste/test_acompanhamento_graus.py`.

- [x] **Passo 1 — Escrever os testes falhando** para GET da edição e do detalhe local, afirmando ausência de inputs e rótulos das datas antigas.
- [x] **Passo 2 — Verificar RED:** os dois testes falharam porque os campos ainda eram exibidos.
- [x] **Passo 3 — Implementar mínimo:** removidos os três campos dos templates locais e do fixture local. `_CAMPOS_DATA` foi atualizado na Tarefa 1; GPRB externo permanece intocado.
- [x] **Passo 4 — Verificar GREEN:** `17 passed, 9 skipped` em acompanhamento/schema e testes de membros.

### Tarefa 3: Gerenciar múltiplos registros Grau + Data no membro

**Arquivos:** criar `contatos/forms_graus.py`; alterar `contatos/models.py` e gerar migration com `CheckConstraint` `grau_numero_4_33`; alterar `contatos/views/gprb_membros.py`, `contatos/templates/contatos/membro_editar.html`; atualizar `teste/test_membro_grau_web.py`; adicionar testes em `teste/test_acompanhamento_graus.py`.

**Interface produzida:** `GrauMembroFormSet` vinculado a um `Membro`, com campos `grau` e `data`; queryset estritamente limitado a `membro.graus`; `tenant_id` persistido sempre de `membro.tenant_id`.

- [x] **Passo 1 — Escrever testes RED:**
  - `test_editar_membro_grava_varios_graus_com_datas_independentes` envia graus 10, 11 e 18 com três datas e confere três linhas e datas exatas.
  - `test_editar_membro_edita_e_remove_linha_de_grau` altera data e remove uma linha por DELETE.
  - `test_formset_rejeita_grau_duplicado_sem_salvar_parcialmente` envia duplicidade e confirma que nenhum registro foi modificado.
  - `test_formset_rejeita_data_vazia_sem_salvar_parcialmente` cobre obrigatoriedade da data.
  - `test_formset_rejeita_data_futura_sem_salvar_parcialmente` usa amanhã como data inválida.
  - `test_formset_rejeita_grau_fora_da_faixa_4_33` cobre limite do catálogo/modelo.
  - `test_formset_rejeita_id_de_historico_de_outro_membro` comprova rejeição e ausência de alteração em registro alheio.
- [x] **Passo 2 — Verificar RED:** os testes falharam: múltiplos graus não eram salvos, atualização/remoção não ocorria, datas/duplicatas eram aceitas e o catálogo não restringia 4–33.
- [x] **Passo 3 — Implementar mínimo:** criado `GrauMembroFormSet`, validação de datas/duplicatas/tenant, `transaction.atomic()`, gestão dinâmica de linhas, constraint `4 <= Grau.numero <= 33` e migration `0025_grau_grau_numero_4_33.py`.
- [x] **Passo 4 — Verificar GREEN:** `25 passed, 9 skipped` nos testes focados de histórico, membros e migração.
- [x] **Passo 5 — Verificar integridade:** testes de banco para graus 3 e 34 passam como rejeitados; Django check, migrations check e Ruff passam.

### Tarefa 4: Limpar histórico de teste somente sob confirmação explícita

**Arquivos:** criar `contatos/management/commands/limpar_historico_graus_teste.py`, `teste/test_acompanhamento_graus.py`.

- [x] **Passo 1 — Escrever e verificar RED** `test_limpeza_graus_command_is_registered`: falhou porque o comando ainda não estava registrado.
- [x] **Passo 2 — Implementar registro mínimo:** criado o comando com flag `--confirm`; o teste de registro passou.
- [x] **Passo 3 — Escrever e verificar RED** dos comportamentos dry-run/confirmado: dry-run não informava contagem e `--confirm` deixava os registros intactos.
- [x] **Passo 4 — Implementar mínimo:** sem confirmação só conta/informa; `--confirm` apaga os registros `GrauMembro` e informa a quantidade; nunca chamado em migration, startup ou workflow.
- [x] **Passo 5 — Verificar GREEN:** os três testes do comando passaram; dry-run preserva a linha e confirmação remove as duas linhas de teste.
- [x] **Limpeza autorizada do banco local:** dry-run em `gprbr-db` pela porta 5434 encontrou 9 registros; `--confirm` removeu 9; novo dry-run confirmou 0 restantes. Nenhuma outra tabela foi alterada.

### Tarefa 5: Criar consulta e página Acompanhamento

**Arquivos:** criar `contatos/views/acompanhamento.py`, `contatos/templates/contatos/acompanhamento.html`; alterar `contatos/membros_urls.py`, `contatos/views/__init__.py`; criar/alterar `teste/test_acompanhamento_graus.py`.

**Interface produzida:** view GET `acompanhamento(request)`; query params allowlist `vale`, `loja`, repetidos `grau`, `ordenar ∈ {nome, vale, loja, grau}`, `direcao ∈ {asc, desc}`, `page`. Contexto de linha inclui membro, presença e datas por número de grau 4–33; Vale/Loja continuam filtros, mas não são colunas da tabela.

- [x] **Passo 1 — Escrever testes RED:** criados testes para rota, 30 colunas/datas, ausência das colunas Vale/Loja, filtro multi-grau OR, filtro Vale/Loja, ordenação, isolamento comum/admin, paginação de 20 e grupo de filtros Vale/Loja/Graus.
- [x] **Passo 2 — Verificar RED:** `resolve()` mostrou a rota dinâmica `detalhe`; GET levanta erro convertendo `acompanhamento` em ID numérico. A página ainda não existe.
- [x] **Passo 3 — Implementar mínimo:** view tenant-scoped, filtros GET validados (graus OR), ordenação allowlist, paginação preservando parâmetros, prefetch de relações e tabela de graus com rolagem horizontal.
- [x] **Passo 4 — Verificar GREEN:** a suíte focada passou `47 passed, 9 skipped`; graus sem data exibem `—` e os três filtros primários compartilham a linha responsiva.
- [x] **Passo 5 — Verificar query budget:** sem prefetch, RED mediu 16 consultas para 1 membro e 136 para 25; com prefetch, GREEN dentro do limite `consultas_25 <= consultas_1 + 3`.

### Tarefa 6: Aplicar o indicador de presença e o limite de 50%

**Arquivos:** `contatos/views/acompanhamento.py`, `contatos/templates/contatos/acompanhamento.html`, `teste/test_acompanhamento_graus.py`.

- [x] **Passo 1 — Escrever teste RED** com membros em 49%, exatamente 50% e sem chamadas; validar classes/atributos renderizados.
- [x] **Passo 2 — Verificar RED:** o teste falhou porque o HTML não marcava nome/percentual da presença.
- [x] **Passo 3 — Implementar mínimo:** reutilizada a saída de `PresencaServico.percentuais`; nome vermelho somente quando valor não nulo e `< 50`, neutro para 50 e ausência de chamadas.
- [x] **Passo 4 — Verificar GREEN:** suite `teste/test_acompanhamento_graus.py` → 20 passed; fórmula de presença existente não foi alterada.

### Tarefa 7: Trocar somente o item do menu

**Arquivos:** `acesso/context_processors.py`, `contatos/membros_urls.py` se necessário, `teste/test_header_branding.py` ou novo `teste/test_acompanhamento_graus.py`.

- [x] **Passo 1 — Escrever testes RED** de menu e permanência da rota Financeiro.
- [x] **Passo 2 — Verificar RED:** falhou porque `Acompanhamento` não estava no menu e `Financeiro` ainda aparecia.
- [x] **Passo 3 — Implementar mínimo:** menu agora aponta para `membros:acompanhamento`; removido só o item Financeiro e seu ícone da navegação, preservando URL/view.
- [x] **Passo 4 — Verificar GREEN:** ambos os testes de navegação passaram; `contatos:financeiro` continua resolvendo.

### Tarefa 8: Remover colunas Vale/Loja e paginar 20 linhas

**Arquivos:** `contatos/views/acompanhamento.py`, `contatos/templates/contatos/acompanhamento.html`, `teste/test_acompanhamento_graus.py`.

- [x] **Passo 1 — Escrever testes RED:** `test_acompanhamento_tabela_remove_colunas_de_vale_e_loja` e `test_acompanhamento_pagina_vinte_e_preserva_filtros`.
- [x] **Passo 2 — Verificar RED:** antes da correção havia 34 colunas visíveis e `Paginator` usava 25 membros por página.
- [x] **Passo 3 — Implementar mínimo:** tirar as colunas/valores Vale e Loja, manter seus filtros e definir página de 20; manter cabeçalhos ordenáveis de Nome/Grau.
- [x] **Passo 4 — Verificar GREEN:** `50 passed, 9 skipped` na suite focada após remoção das colunas e paginação em 20.

### Tarefa 9: Garantir CSS compilado no Docker

**Arquivos:** `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `.github/workflows/ci.yml`.

- [x] **Passo 1 — Verificar RED:** o bundle servido pelo container não continha `minmax(0,2fr)`; o container não gerava Tailwind. Build inicial revelou também entrypoint CRLF e diretórios de runtime criados com brace expansion incompatível com `/bin/sh`.
- [x] **Passo 2 — Implementar build de assets:** adicionado estágio Node com `npm ci` + `npm run build`, excluído `node_modules` do contexto e copiado `theme/static/css` para a imagem final.
- [x] **Passo 3 — Incluir assets na imagem:** `collectstatic` roda durante o build Docker, o entrypoint é normalizado/validado e o bind mount de `staticfiles` foi removido.
- [x] **Passo 4 — Cobrir no CI:** o workflow constrói a imagem Docker e valida que `/app/staticfiles/css/dist/styles.css` contém a regra CSS da linha de filtros.
- [x] **Passo 5 — Verificar GREEN:** container healthy; CSS servido HTTP 200 (61.818 bytes) e contém a regra; `/membros/acompanhamento/` redireciona ao login sem sessão.

### Tarefa 10: Adicionar presets de seleção de graus

**Arquivos:** `contatos/views/acompanhamento.py`, `contatos/templates/contatos/acompanhamento.html`, `teste/test_acompanhamento_graus.py`.

**Faixas:** `perfeicao=4..14`, `rosa_cruz=15..18` (rótulo visível **Capítulo**), `kadosh=19..30`, `consistorio=31..32`, `sc33=33`.

- [x] **Passo 1 — Escrever testes RED:** renderização dos cinco checkboxes; faixa inclusiva; união OR de várias faixas; nenhum corpo selecionado inclui membros sem grau; seleção persistida; preset inválido não amplia resultados.
- [x] **Passo 2 — Verificar RED:** 9 testes falharam antes da implementação, sem controles de presets e sem filtrar por `grupo_grau`.
- [x] **Passo 3 — Implementar mínimo:** allowlist de intervalos no servidor, união OR dos corpos, estado checked preservado e aplicação imediata ao marcar/desmarcar.
- [x] **Passo 4 — Verificar GREEN:** testes de preset passaram; suite focada completa → `59 passed, 9 skipped`, com isolamento por tenant, sem duplicar membros e sem filtrar quando nenhum corpo está marcado.

### Tarefa 11: Corrigir e validar o workflow CI

**Arquivos:** `.github/workflows/ci.yml`, possivelmente `teste/test_acompanhamento_graus.py` para fix de regressões descobertas.

- [x] **Passo 1 — Reproduzir falha de CI:** parser YAML falhou na região da linha 99 por indentação inválida.
- [x] **Passo 2 — Corrigir YAML:** steps reorganizados sob `jobs.test.steps`, ferramentas instaladas no job e YAML validado localmente.
- [x] **Passo 3 — Garantir catálogo antes dos testes:** `seed_graus` idempotente passou nos testes e o CI executa o comando após migrations; não roda no startup.
- [x] **Passo 4 — Adicionar gates de qualidade** ao workflow: Django check, migrations check, Ruff nos arquivos desta feature, Bandit high-severity e pip-audit; scanners não são mascarados.
- [x] **Passo 5 — Validar migrations:** migrations aplicadas no PostgreSQL de teste recriado; schema de `HistoricoCargo.data_passagem` verificado.
- [x] **Passo 6 — Executar testes focados:** `59 passed, 9 skipped` nos testes de acompanhamento, presets, graus, membros e navegação após a verificação final.
- [ ] **Passo 7 — Gate completo pendente:** `pytest teste/` foi executado com `--create-db`; resultado `209 failed, 608 passed, 48 skipped, 13 errors` antes dos últimos ajustes de tabela/layout. GitHub Actions remoto não foi disparado porque não houve push. Falhas listadas em `ci-full-suite-report.md`; não fazer deploy até triagem e CI verde.

### Tarefa 12: Simplificar e aplicar filtros de corpos imediatamente

**Arquivos:** `contatos/templates/contatos/acompanhamento.html`, `teste/test_acompanhamento_graus.py`, `specs/006-acompanhamento-graus/spec.md`.

- [x] Remover o select manual de graus; deixar Filtrar/Limpar logo após os corpos; alternar corpo submete GET imediatamente e mantém Vale/Loja e combinação OR.
- [x] Remover o corpo Todos; nenhum corpo selecionado continua exibindo todos os membros.
- [x] Verificar: testes RED→GREEN; regressão focada `59 passed, 9 skipped`; browser fixture confirmou aplicação imediata, OR e preservação de Vale/Loja; checkbox nativo mantém teclado; grid/flex-wrap mantém reflow responsivo; detector de layout sem findings.

### Tarefa 13: Restringir colunas de grau aos corpos selecionados

**Arquivos:** `contatos/views/acompanhamento.py`, `contatos/templates/contatos/acompanhamento.html`, `teste/test_acompanhamento_graus.py`.

- [x] Escrever testes para cada corpo, união de corpos, seleção vazia (todos os graus) e manutenção das colunas Membro/Presença; conferir o colspan do estado vazio.
- [x] Verificar RED: 6 testes novos falharam porque a tabela ainda renderizava 30 colunas em qualquer filtro.
- [x] Exibir somente as colunas de grau das faixas selecionadas, usando a união para múltiplos corpos; manter o filtro OR das linhas e as colunas fixas.
- [x] Rodar testes de coluna → `8 passed, 31 deselected`; verificação integrada final → `90 passed, 7 deselected`; detector de layout sem findings.

## Verificação final da spec

- Todos os RF-1 a RF-4 têm tarefas e testes correspondentes.
- A limpeza dos dados sintéticos é explícita, confirmada e fora das migrations.
- A remoção de `Membro.data_passagem` não remove `HistoricoCargo.data_passagem`.
- O Financeiro é retirado somente da navegação; seus endpoints continuam disponíveis.
- A implementação foi aprovada pelo usuário; a suite completa permanece como gate pendente antes de merge/deploy.
