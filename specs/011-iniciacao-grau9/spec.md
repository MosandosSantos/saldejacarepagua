# Spec: Candidatos à Iniciação — Grau 9

**Status:** execução autônoma autorizada pelo usuário; decisões e suposições ficam registradas para revisão posterior.

## Objetivo

Exibir, em uma página autenticada e somente de consulta, os membros que atendem aos critérios para candidatura ao Grau 9. A candidatura é derivada do histórico de graus e das chamadas já registradas; a primeira entrega não cria nem persiste candidaturas.

## Decisões de escopo

- Criar uma página separada em `/membros/iniciacao/`, com navegação **Iniciação a Graus**.
- A página existente `/iniciacao/` (Flow comercial de Recepção/Súplica) não será alterada.
- A página `/membros/acompanhamento/` e suas colunas de histórico de grau não serão alteradas.
- A primeira entrega apresenta somente candidatos ao Grau 9. Os outros graus são uma sequência futura, habilitada um por vez quando cada regra entrar em implementação.
- A lista é automática: mudar histórico ou chamadas pode incluir/remover um membro na próxima consulta. Não há status de candidatura, aprovação, recusa, notificação ou escrita de dados.
- A lista é tenant/Vale-scoped, ordenada por Vale e nome, e mostra Vale, nome, data de obtenção do Grau 4 e a presença calculada que justificam a candidatura.

## Requisitos funcionais — primeira entrega

### RF-1 — Critérios de candidatura ao Grau 9

Um membro aparece na lista somente quando **todas** as condições forem atendidas:

1. Situação `ATIVO`.
2. O maior grau registrado no histórico do próprio tenant é exatamente 8.
3. Existe registro do Grau 4 cuja data seja **estritamente anterior** à data local atual menos seis meses de calendário. Na data que completa exatamente seis meses, ainda não qualifica.
4. Presença exata no Vale é ≥50%: chamadas marcadas como presente divididas pelo total de chamadas registradas do membro em eventos de todas as Lojas locais daquele tenant, ao longo de todo o histórico.
5. Uma chamada registrada como ausente conta no denominador; evento sem chamada não conta. Sem nenhuma chamada registrada, o membro não qualifica.
6. O cálculo cruza o tenant do membro com o conjunto de Lojas do mesmo tenant. Presenças de outro Vale/tenant nunca entram no numerador ou denominador.

### RF-2 — Apresentação

- Uma única seção/coluna chamada **Candidatos ao Grau 9**.
- Cada candidato mostra Vale, nome, data do Grau 4 e percentual de presença do Vale.
- Comparação com 50% usa a razão exata antes de arredondar o valor apresentado.
- Sem candidatos, mostrar um estado vazio claro: “Nenhum membro atende aos critérios para o Grau 9 no momento.”
- Nenhuma ação altera o histórico ou cria um registro de candidatura.

### RF-3 — Acesso e localização

- Exigir sessão autenticada e Vale ativo, seguindo o padrão de `/membros/acompanhamento/`.
- Usuário comum vê somente os membros do tenant autorizado; `admin_saas` segue o contexto e o comportamento de escopo do Acompanhamento.
- A nova rota usa o namespace `membros` e não conflita com `/iniciacao/`.
- O item de navegação fica ativo somente na nova rota, sem marcar Acompanhamento como ativo ao mesmo tempo.

## Regras futuras informadas — não implementar nesta fase

| Grau candidato | Condições já informadas para etapas posteriores |
|---|---|
| 14 | Grau atual 13; pelo menos 6 meses desde o Grau 9; presença ≥50% no Vale desde a data do Grau 4. |
| 15 | Grau atual 14; pelo menos 6 meses no Grau 14; pelo menos 2 presenças após a data do Grau 14. |
| 18 | Grau atual 15; pelo menos 6 meses desde o Grau 15; presença ≥50% no Vale desde a data do Grau 15. |
| 19 | Grau atual 18; pelo menos 2 presenças após a data do Grau 18. |
| 22 | Grau atual 21; presença ≥50% combinando as Lojas às quais o membro está vinculado. |
| 28 | Grau atual 27; pelo menos 4 meses desde o Grau 22; presença ≥50% combinando as Lojas vinculadas. |
| 30 | Grau atual 29; pelo menos 4 meses desde o Grau 28; presença ≥50% combinando as Lojas vinculadas. |
| 31 | Grau atual 30; pelo menos 6 meses desde o Grau 30; sem requisito de presença. |
| 32 | Grau atual 31; pelo menos 6 meses desde o Grau 31; sem requisito de presença. |
| 33 | Grau atual 32; pelo menos 1 ano desde o Grau 32; sem requisito de presença. |

Para 22/28/30, a presença futura combina chamadas de todas as Lojas às quais o membro esteja vinculado. O Grau 19 foi adicionado ao roteiro futuro por ter recebido uma regra explícita, apesar de não constar na lista inicial.

## Arquitetura

- `contatos/iniciacao_graus.py` (novo): cálculo isolado da elegibilidade e dados de apresentação do candidato, incluindo o rótulo do Vale.
- `contatos/views/iniciacao_graus.py` (novo): autenticação, escopo do Vale/tenant e renderização.
- `contatos/membros_urls.py` e `contatos/views/__init__.py`: nova rota `iniciacao/`.
- `contatos/templates/contatos/iniciacao_graus.html` (novo): lista de candidatos e estado vazio.
- `acesso/context_processors.py`: novo item **Iniciação a Graus** e destaque independente de Acompanhamento.
- `teste/test_iniciacao_graus.py` (novo): regras de elegibilidade, tenant, vista e navegação.
- Nenhum modelo, schema, migration ou dependência nova.

## Stack, estilo e comandos

- Django 5.2, Python 3.13, PostgreSQL, templates Django/Tailwind HAZON e pytest-django.
- Usar `python-dateutil` já listado em `requirements.txt` para subtração de meses de calendário.
- Seguir o estilo HAZON existente: página Operate, densidade legível, tabela/lista simples, estados vazios e valores numéricos em mono.
- Testes focados: `python -m pytest teste/test_iniciacao_graus.py --ds=core.settings_vale_test --reuse-db -q` com `VALE_TEST_DATABASE_URL` apontando ao PostgreSQL isolado de testes.
- Verificações: Ruff dos arquivos alterados; `docker exec gprbr-app python manage.py check`; `docker exec gprbr-app python manage.py makemigrations --check --dry-run`; build Docker local e `/healthz/`.

## Estratégia de testes

- RED/GREEN para maior grau exatamente 8; grau 4 inexistente, recente, exatamente seis meses e mais de seis meses.
- RED/GREEN para presença sem chamadas, abaixo de 50%, exatamente 50% e acima de 50%.
- Confirmar que várias Lojas do mesmo Vale são combinadas sem duplicação e que eventos de outra tenant/loja não contaminam o cálculo.
- Confirmar usuário comum, administrador com contexto permitido, loja/tenant externo, acesso sem Vale ativo e ausência de candidatos.
- Confirmar conteúdo (nome, data do Grau 4, presença), ordenação alfabética, nova rota e item de navegação ativo.
- Não alterar as regras existentes do Flow comercial, do Acompanhamento ou das exportações PDF/XLSX.

## Limites e suposições para revisão

- **Sempre:** calcular do histórico real `GrauMembro` e das chamadas `PresencaEvento`; escopar membros, chamadas e Lojas pelo tenant no servidor; não criar candidatura persistente.
- **Não fazer nesta fase:** candidaturas para outros graus, mudança do Flow `/iniciacao/`, alteração do Acompanhamento, ações de aprovação, status, notificações, exportação ou migration.
- **Suposição de negócio:** candidatos precisam estar `ATIVO`; embora não tenha sido pedido explicitamente, um membro inativo não é tratado como elegível para nova iniciação.
- **Suposição de dados:** presença Vale-wide usa apenas eventos cujos `loja_id` correspondem a Lojas locais do mesmo tenant; identificadores externos que não resolvam a uma Loja local ficam fora do cálculo.
- **Suposição temporal:** regras de “6 meses”, “4 meses” e “1 ano” futuras usam meses/anos de calendário; somente a regra de 9, que diz “mais de seis meses”, é estritamente `>`.

## Critérios de sucesso

1. `/membros/iniciacao/` lista exatamente os membros ativos com maior grau 8, Grau 4 há mais de seis meses e presença exata ≥50% no Vale.
2. Cada candidato mostra Vale, nome, data de obtenção do Grau 4 e presença usada no cálculo.
3. Nenhum dado de outro tenant afeta o resultado ou aparece na página.
4. A ausência de histórico de chamadas impede a candidatura; igualdade exata a 50% qualifica.
5. A página e o item de navegação são distintos do Flow comercial `/iniciacao/` e do Acompanhamento.
6. Testes focados, Ruff, Django check, migrations check, build e healthcheck são executados; falhas conhecidas da suíte completa são reportadas separadamente, sem atribuição causal sem investigação.
