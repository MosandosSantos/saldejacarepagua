# Pirâmide de Graus — Plano de Implementação

> **Para agentes de implementação:** usar `executing-plans` para executar este plano tarefa por tarefa. O repositório e a tecnologia de destino ainda não foram informados; a Tarefa 1 mapeia os caminhos lógicos deste plano para a estrutura real antes de qualquer alteração de código.

**Objetivo:** reproduzir em outra aplicação a Pirâmide de Graus do dashboard, com classificação correta por maior grau, isolamento por tenant, cinco faixas estáveis, legenda e SVG 3D.

**Arquitetura:** separar a consulta tenant-scoped, a transformação de graus máximos em cinco contagens e a apresentação. A consulta retorna no máximo um grau máximo por Membro ativo; a função de domínio constrói o contrato fixo da pirâmide; o componente apresenta o SVG e uma legenda textual. O rótulo de grau 33 no destino será SC33, conforme decisão do usuário.

**Stack:** deliberadamente independente de linguagem/framework. Usar o ORM, sistema de autenticação, componentes e runner de testes que já existirem na aplicação destino; não adicionar dependências gráficas sem necessidade.

**Spec:** `specs/009-piramide-graus/spec.md`

## Restrições globais

- Faixas fixas: 4–14 Perfeição, 15–18 Capítulo, 19–30 Kadosh, 31–32 Consistório e 33 SC33.
- Considerar somente Membros ativos e históricos de grau do mesmo tenant.
- Classificar cada Membro pelo maior grau registrado; Membro sem histórico não entra no total.
- Retornar cada Membro no máximo uma vez e manter as cinco faixas, inclusive as vazias.
- O total é a soma das contagens de Membros elegíveis, não de todos os Membros ativos.
- Percentual = arredondamento de `contagem / total * 100`; para total zero, percentual zero. Para paridade com o fonte, empates seguem `round` de Python (ties-to-even).
- A largura da fatia representa a posição hierárquica, não a contagem.
- Preservar autorização por tenant no servidor; ausência de tenant não concede acesso global por si só.
- A interface de destino exibe SC33; a implementação fonte ainda chama o topo de SCREAA.
- Manter a solução neutra em dependências: não adicionar biblioteca de gráficos sem demonstrar necessidade no projeto de destino.

## Review Focus

- Duas ou mais linhas de grau para o mesmo Membro: a consulta deve retornar o máximo e uma só linha — teste na Tarefa 3.
- Histórico de outro tenant associado indevidamente: excluir a linha e impedir vazamento entre tenants — teste na Tarefa 3.
- Membro inativo ou sem histórico: excluir da pirâmide sem excluir Membros ativos com histórico válido — testes nas Tarefas 2–3.
- Total zero e faixas sem ocorrência: retornar/renderizar cinco faixas com zero, sem divisão por zero — testes nas Tarefas 2 e 4.
- Limites 14/15, 18/19, 30/31 e 32/33: classificar no intervalo inclusivo correto — teste na Tarefa 2.

---

## Mapa lógico de arquivos no destino

Como o repositório externo não foi fornecido, os nomes abaixo são responsabilidades, não caminhos presumidos. A Tarefa 1 registra os caminhos equivalentes reais.

| Unidade lógica | Responsabilidade |
|---|---|
| Serviço/repositório de graus | Buscar Membros ativos e o maior grau do histórico, limitado ao escopo autorizado. |
| Domínio da pirâmide | Converter uma entrada de graus máximos no resumo com cinco faixas, percentuais e cores. |
| Componente da pirâmide | Renderizar SVG 3D, rótulos, contagens e legenda acessível. |
| Dashboard | Passar o tenant autorizado, tratar erro/estado vazio e apresentar o total. |
| Testes de domínio, consulta e interface | Cobrir classificação, isolamento, vazio, acessibilidade e desenho. |

### Tarefa 1 — Mapear a aplicação de destino e fechar interfaces

**Arquivos:** documentação/README/schema de dados e configuração de testes já existentes no repositório de destino; registrar o mapa no próprio plano ou no ticket externo.

**Interfaces produzidas:**
- Campos reais que representam Membro, situação, tenant, histórico e número do grau.
- Mecanismo confiável para derivar `TenantScope` da sessão/usuário autorizado.
- Caminhos reais para serviço/repositório, componente do dashboard e testes.
- Comandos exatos de teste e build da aplicação destino.

- [ ] **Passo 1: Inspecionar schema e autenticação** — localizar as três entidades da spec e identificar onde o tenant permitido é resolvido no servidor.
- [ ] **Passo 2: Mapear a estrutura** — registrar caminhos de domínio, consulta, UI e testes sem criar um módulo paralelo ao padrão existente.
- [ ] **Passo 3: Definir o adaptador mínimo** — documentar como o repositório obterá `memberId`, `tenantId`, situação ativa e histórico de graus.
- [ ] **Passo 4: Validar comandos de projeto** — executar e registrar os comandos reais de teste/build; confirmar que usam apenas recursos de teste.
- [ ] **Aceite:** uma pessoa implementadora consegue apontar para os caminhos e comandos reais sem escolher stack, autenticação ou schema por suposição.

### Tarefa 2 — Implementar o agregador de domínio com TDD

**Arquivos:** criar/alterar a unidade lógica de domínio da pirâmide e seu módulo de testes, nos caminhos mapeados na Tarefa 1.

**Interface produzida:** função pura equivalente a `buildDegreePyramid(highestDegrees) -> PyramidSummary`, onde `highestDegrees` contém um `{memberId, maxDegree}` por Membro ativo já no escopo autorizado. `PyramidSummary` contém `total` e exatamente cinco `faixas` com `minimo`, `maximo`, `nome`, `rotulo`, `total`, `percentual` e `cor`.

- [ ] **Passo 1: Escrever testes RED** — cobrir limites 14/15, 18/19, 30/31 e 32/33; graus 4 e 33; contagem de máximos únicos; total zero; faixas vazias; percentuais com arredondamento definido.
- [ ] **Passo 2: Executar somente os testes novos** — usar o comando anotado na Tarefa 1 e confirmar falha pelas regras ausentes.
- [ ] **Passo 3: Implementar as cinco faixas em ordem fixa** — aplicar intervalos inclusivos da spec, labels (incluindo SC33), cores explícitas por faixa e total derivado das contagens.
- [ ] **Passo 4: Verificar GREEN e refatorar** — repetir os testes; confirmar que o arredondamento de empate é documentado/compatível e que total zero não divide por zero.
- [ ] **Aceite:** a mesma entrada produz o mesmo resumo, sem acesso a banco, sessão ou UI dentro da função de domínio.

### Tarefa 3 — Criar a consulta tenant-scoped de graus máximos

**Arquivos:** criar/alterar a unidade de repositório/serviço e testes de integração no destino.

**Interface produzida:** operação equivalente a `loadActiveMemberHighestDegrees(scope: TenantScope) -> Iterable<MemberHighestDegree>`. `scope` deve vir da autorização do servidor, nunca diretamente de um tenant enviado pelo cliente.

- [ ] **Passo 1: Escrever testes RED de consulta** — criar Membros ativos/inativos em dois tenants, históricos próprios e estrangeiros, vários graus para o mesmo Membro e Membros sem histórico; afirmar que cada Membro elegível aparece uma vez com seu maior grau.
- [ ] **Passo 2: Executar os testes e verificar RED** — confirmar que o comportamento atual do destino não atende ao escopo/agrupamento.
- [ ] **Passo 3: Consultar maior grau por Membro** — agregar `MAX(grau.numero)` por identificador do Membro, limitar situação a ativa e relacionar histórico pelo mesmo tenant; retornar um resultado por Membro.
- [ ] **Passo 4: Testar isolamento** — tenant A não recebe Membros nem históricos do tenant B; escopo global, se existir para perfil privilegiado, deve ser explicitamente autorizado.
- [ ] **Passo 5: Verificar GREEN e custo de consulta** — repetir os testes e inspecionar o plano/contagem de consultas para evitar uma consulta por Membro.
- [ ] **Aceite:** a saída da consulta pode ser entregue diretamente ao agregador da Tarefa 2 e nunca contém Membro inativo, sem grau ou fora do escopo.

### Tarefa 4 — Renderizar a pirâmide, legenda e estados vazios

**Arquivos:** criar/alterar o componente SVG/visual, estilos locais e testes de renderização no destino.

**Interface consumida:** `PyramidSummary` produzido pelas Tarefas 2–3. A UI não recalcula contagens nem aplica autorização.

- [ ] **Passo 1: Escrever testes RED de apresentação** — cinco faixas ordenadas, label SC33, contagens/percentuais na legenda, total, cores esperadas e total zero.
- [ ] **Passo 2: Escrever testes de segurança visual** — rótulos com caracteres especiais devem ser escapados; nenhuma entrada textual deve virar markup SVG executável.
- [ ] **Passo 3: Implementar o SVG** — desenhar as faixas do topo à base a partir da ordem lógica base→topo; largura depende da posição, usando as dimensões de referência e a sequência explícita de cores da spec.
- [ ] **Passo 4: Implementar legenda textual e responsividade** — mostrar intervalo, rótulo, contagem e percentual; manter uma alternativa textual legível quando SVG não puder ser lido.
- [ ] **Passo 5: Tratar estados** — cinco faixas zeradas quando não há Membros elegíveis; falha de consulta deve exibir estado seguro sem trocar tenant nem inventar totais.
- [ ] **Passo 6: Verificar GREEN** — executar testes de apresentação e conferir em viewport estreito e largo no app de destino.
- [ ] **Aceite:** SVG e legenda exibem a mesma ordem/contagens; largura não implica escala por volume; estados vazio/erro continuam compreensíveis.

### Tarefa 5 — Integrar ao dashboard e verificar o fluxo completo

**Arquivos:** view/rota do dashboard e testes end-to-end ou de integração já usados pelo destino.

- [ ] **Passo 1: Escrever teste RED do fluxo** — sessão tenant A exibe só A; perfil autorizado sem tenant exibe apenas o escopo global permitido; filtro adulterado não amplia acesso.
- [ ] **Passo 2: Integrar serviço ao dashboard** — obter escopo autorizado no servidor, chamar repositório, agregador e componente sem acoplar UI ao ORM.
- [ ] **Passo 3: Cobrir estado vazio e erro** — verificar total zero sem histórico e fallback seguro quando o repositório falha.
- [ ] **Passo 4: Executar a suíte vertical** — rodar testes de domínio, repositório, integração e renderização; rodar build do destino.
- [ ] **Aceite:** dashboard mostra dados do escopo autorizado, sem vazamento, total consistente e a faixa 33 com label SC33.

### Tarefa 6 — Entregar documentação operacional no app destino

**Arquivos:** documentação do dashboard e instruções de manutenção no projeto externo.

- [ ] Registrar os cinco intervalos, política de maior grau, tenant scope, exclusão de Membros sem histórico, fórmula de percentuais e convenção de arredondamento.
- [ ] Registrar a diferença de nomenclatura do sistema fonte (SCREAA) e a decisão de usar SC33 no destino.
- [ ] Registrar comandos reais de teste/build e como atualizar as faixas sem alterar silenciosamente a regra de contagem.
- [ ] **Aceite:** uma pessoa mantenedora consegue explicar por que o total pode ser menor que o total de Membros ativos e reproduzir a classificação de um Membro manualmente.

## Verificação final do plano

- A Tarefa 1 resolve a ausência de informações do app externo antes de escolher caminhos ou comandos.
- As regras de dados estão cobertas nas Tarefas 2–3; apresentação na Tarefa 4; tenant/error flow na Tarefa 5; manutenção na Tarefa 6.
- Nenhuma tarefa assume linguagem, framework, banco ou biblioteca gráfica que o usuário não informou.
- A implementação do destino não faz parte deste plano neste repositório; este arquivo é o roteiro de transferência e implementação.
