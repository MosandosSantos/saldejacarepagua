# Tasks: Pirâmide de Graus

**Entrada:** `spec.md` e `plan.md` deste diretório.

**Pré-requisito:** escolher/fornecer o repositório de destino. A Tarefa T001 mapeia os caminhos lógicos abaixo para a estrutura real; não iniciar código antes desse mapeamento.

**Testes:** aplicar TDD. Os caminhos `src/dashboard/degree-pyramid/` e `tests/dashboard/degree-pyramid/` são nomes lógicos sugeridos, não pressupõem linguagem ou framework.

**Organização:** uma história independente, US1 (P1), cobrindo consulta tenant-scoped, cálculo e visualização.

## Fase 1: Setup

**Objetivo:** entender o app destino e registrar os pontos de integração.

- [ ] T001 Mapear modelos, autenticação/tenant, dashboard, testes e comandos do app destino; registrar caminhos reais e contrato adaptado em `docs/degree-pyramid/target-map.md` no app destino.

## Fase 2: Fundacional

**Objetivo:** definir o contrato entre consulta, cálculo e interface antes das partes dependentes.

- [ ] T002 Definir o tipo/DTO `PyramidSummary` em `src/dashboard/degree-pyramid/contract` com `total` e cinco `faixas` (`minimo`, `maximo`, `nome`, `rotulo`, `total`, `percentual`, `cor`), mapeando o JSON de `spec.md` para a linguagem destino.

## Fase 3: US1 — Consultar a distribuição de graus (P1)

**Objetivo:** exibir, para o tenant autorizado, os Membros ativos agrupados pelo maior grau do histórico.

**Teste independente:** com dados de dois tenants, validar contagem e exclusões pela consulta; validar os cinco intervalos no serviço; abrir o dashboard e conferir SVG, legenda, total e estado vazio.

### Testes de US1

- [ ] T003 [P] [US1] Criar testes unitários em `tests/dashboard/degree-pyramid/domain` para limites 14/15, 18/19, 30/31, 32/33, graus extremos 4/33, cinco faixas, total zero e percentuais/arredondamento.
- [ ] T004 [P] [US1] Criar testes de integração em `tests/dashboard/degree-pyramid/repository` para ativo/inativo, Membro sem histórico, graus múltiplos do mesmo Membro, histórico de tenant diferente e escopo autorizado de tenant.
- [ ] T005 [P] [US1] Criar testes de componente em `tests/dashboard/degree-pyramid/ui` para ordem, label SC33, cores, contagens, percentuais, total, legenda textual e escape de rótulos no SVG.

### Implementação de US1

- [ ] T006 [P] [US1] Implementar `buildDegreePyramid(highestDegrees) -> PyramidSummary` em `src/dashboard/degree-pyramid/domain`; usar os cinco intervalos fixos, contar uma vez por Membro, calcular total/percentuais e zerar percentuais quando o total for zero.
- [ ] T007 [P] [US1] Implementar `loadActiveMemberHighestDegrees(scope) -> Iterable<MemberHighestDegree>` em `src/dashboard/degree-pyramid/repository`; filtrar Membros ativos e escopo autorizado, usar apenas históricos do mesmo tenant e retornar uma linha por Membro com `MAX(grau.numero)`.
- [ ] T008 [US1] Integrar o serviço ao dashboard em `src/dashboard/degree-pyramid/dashboard-adapter`; derivar `scope` da sessão/usuário no servidor, compor repositório + agregador e registrar erros sem consultar outro tenant como fallback.
- [ ] T009 [P] [US1] Implementar o SVG 3D em `src/dashboard/degree-pyramid/ui/pyramid-svg`; usar a sequência base→topo definida na spec, desenhar do topo à base, dimensionar fatias pela posição e exibir contagem no SVG.
- [ ] T010 [P] [US1] Implementar legenda e estado vazio em `src/dashboard/degree-pyramid/ui/pyramid-legend`; exibir intervalo, rótulo, contagem, percentual e total, manter cinco faixas com zero e oferecer alternativa textual ao SVG.
- [ ] T011 [US1] Conectar componente e adaptador à página existente em `src/dashboard`; preservar o estilo e layout do app destino, sem introduzir filtro por Loja, Corpo, Rito ou potência.
- [ ] T012 [US1] Executar os testes de domínio, repositório, componente e fluxo do dashboard; corrigir falhas e verificar que os comandos registrados em `docs/degree-pyramid/target-map.md` passam.

## Fase 4: Polish e manutenção

**Objetivo:** assegurar acessibilidade, segurança visual e manutenção da regra.

- [ ] T013 [P] Atualizar a documentação do dashboard no app destino para registrar faixas, escopo tenant, regra do maior grau, exclusão de Membros sem histórico e diferença de nomenclatura SCREAA→SC33 em `docs/degree-pyramid/README.md`.
- [ ] T014 [P] Revisar acessibilidade/responsividade e escape de SVG em `src/dashboard/degree-pyramid/ui`; validar viewport estreito/largo e conteúdo com caracteres especiais.
- [ ] T015 Executar a suíte completa e build do app destino; registrar resultados em `docs/degree-pyramid/README.md` sem alterar os limites ou o significado do total.

## Dependências e ordem

```text
T001 → T002 → (T003 || T004 || T005) → T006 + T007 → T008 → T009 + T010 → T011 → T012 → T013 + T014 → T015
```

- **T001** é obrigatório: resolve a ausência do repositório/stack destino e substitui caminhos lógicos pelos caminhos reais.
- **T002** bloqueia as tarefas de cálculo e UI porque define o contrato comum.
- **T003, T004 e T005** podem ser escritos em paralelo depois de T002; são arquivos de teste distintos.
- **T006 e T007** podem ser implementados em paralelo depois que seus testes RED estiverem escritos; T008 integra ambos.
- **T009 e T010** podem ser trabalhados em paralelo após o contrato visual estar definido; T011 integra a página.
- **T012** é o gate vertical; documentação e polish finais vêm depois.
- **T013 e T014** podem ser finalizados em paralelo depois do fluxo vertical T012, pois alteram documentação e UI, respectivamente.

### Exemplo de paralelismo para US1

Depois de T001–T002, podem ser iniciados em paralelo:

- T003: testes unitários do domínio.
- T004: testes de integração do repositório.
- T005: testes de renderização da UI.

Depois que os testes RED estiverem definidos, T006 e T007 podem ser implementados em paralelo; T008 espera ambos. T009 e T010 são componentes distintos e podem avançar em paralelo antes de T011. Depois de T012, T013 e T014 também podem avançar em paralelo.

## Estratégia de entrega

1. **MVP:** completar T001–T008 e provar por teste o escopo autorizado e a contagem correta.
2. **Apresentação:** completar T009–T011 e verificar SVG, legenda e estado vazio.
3. **Pronto para transferência:** completar T012–T015 e entregar o app com documentação e suíte/build verificados.

## Critérios independentes de aceite de US1

- Um Membro com histórico 4º, 14º e 18º conta uma vez na faixa 15–18.
- Um Membro inativo, sem histórico ou com histórico de tenant diferente não é contado.
- Os limites de grau são inclusivos e cada resultado cai numa só faixa.
- As cinco faixas aparecem mesmo com contagem zero; com total zero, percentual é zero.
- A soma das contagens é o total; percentuais podem somar diferente de 100 por arredondamento.
- SC33 aparece no topo; legenda e SVG exibem as mesmas contagens.
- A largura representa ordem hierárquica, nunca volume de Membros.
