# Tasks: Exportação do Acompanhamento

**Entrada:** `spec.md` e `plan.md` deste diretório.

**História:** US1 (P1) — exportar o Acompanhamento filtrado em PDF e XLSX.

**Testes:** obrigatórios, seguindo RED → GREEN. A configuração usa `core.settings_vale_test` e `VALE_TEST_DATABASE_URL` para o PostgreSQL local em `127.0.0.1:5434`.

## Fase 1: Setup

**Objetivo:** confirmar os recursos já existentes sem adicionar dependências.

- [ ] T001 Verificar ReportLab e openpyxl em `requirements.txt`, settings de teste em `core/settings_vale_test.py` e baseline focado em `teste/test_acompanhamento_graus.py`.
  - Aceite: as duas bibliotecas já estão disponíveis; nenhum pacote novo é instalado.
  - Verificar: executar os testes de Acompanhamento com `VALE_TEST_DATABASE_URL` no banco local de testes.

## Fase 2: Fundacional

**Objetivo:** não há migração ou schema a criar; T001 confirma as dependências. O contrato compartilhado de consulta é implementado na US1 antes dos renderizadores.

## Fase 3: US1 — Exportar relatório filtrado (P1)

**Objetivo:** permitir que o usuário autorizado obtenha todos os resultados dos filtros correntes em PDF A4 paisagem ou XLSX, sem vazamento entre tenants.

**Teste independente:** criar mais de 20 Membros distribuídos por dois tenants, filtrar e verificar que ambos os arquivos contêm todas e somente as linhas autorizadas, as mesmas colunas/sort da tela e as datas em mês/ano.

### Testes e implementação de US1

- [ ] T002 [US1] Escrever testes RED para `_resolver_consulta_acompanhamento` e `_linhas_acompanhamento` em `teste/test_acompanhamento_exportacao.py` cobrindo Vale + Loja + Corpo/grau, OR, colunas visíveis, ordenação e uma linha por Membro.
  - Aceite: os testes falham porque ainda não há interface compartilhada.
  - Verificar: executar os testes nomeados antes de implementar.
- [ ] T003 [US1] Extrair `_resolver_consulta_acompanhamento(request, tenant_ids)` e `_linhas_acompanhamento(membros, graus_visiveis)` em `contatos/views/acompanhamento.py`; manter a paginação de 20 somente no HTML.
  - Aceite: a view HTML e exportação usarão a mesma QuerySet ordenada e o mesmo conjunto de graus.
  - Verificar: `teste/test_acompanhamento_graus.py` continua verde, incluindo filtros, ordenação, colunas e paginação.
- [ ] T004 [US1] Escrever testes RED da view de exportação em `teste/test_acompanhamento_exportacao.py` para PDF/XLSX, formato desconhecido, Vale inativo, filtro adulterado, tenant A/B e 21+ registros; afirmar que `page=2` não limita exportação.
  - Aceite: os testes definem Content-Type/disposição, escopo e ausência de paginação.
  - Verificar: confirmar falha por rota/view ausente antes da implementação.
- [ ] T005 [US1] Criar `acompanhamento_exportar(request, formato)` em `contatos/views/acompanhamento_exportacao.py`; registrar `acompanhamento/relatorio/<str:formato>/` em `contatos/membros_urls.py` e exportar a view em `contatos/views/__init__.py`.
  - Aceite: somente `pdf` e `xlsx` são aceitos; rota exige login e Vale ativo; resultados usam o resolver compartilhado e ignoram `page`.
  - Verificar: executar testes da view; invalid format deve retornar erro sem arquivo e IDs de outro tenant não devem revelar dados.
- [ ] T006 [US1] Escrever testes RED do workbook em `teste/test_acompanhamento_exportacao.py` para aba `Acompanhamento`, cabeçalhos, presença, graus filtrados, datas, autofiltro, `freeze_panes == 'C2'`, resultado vazio e nome iniciado com `=`.
  - Aceite: o leitor openpyxl reabre bytes reais e confirma células de texto não viram fórmulas.
  - Verificar: os testes falham porque o renderizador XLSX ainda não existe.
- [ ] T007 [US1] Implementar `gerar_xlsx_acompanhamento(linhas, graus_visiveis, gerado_em) -> bytes` em `contatos/relatorio_acompanhamento.py`.
  - Aceite: uma planilha em memória; datas reais com formato `mm/yyyy`; cabeçalho/filtros; panes em `C2`; sem escrita em disco.
  - Verificar: reabrir o workbook de resposta com openpyxl e executar testes XLSX.
- [ ] T008 [US1] Escrever testes RED do PDF em `teste/test_acompanhamento_exportacao.py` para assinatura `%PDF-`, MIME, nome, A4 paisagem, grid, repetição do cabeçalho, datas `MM/AAAA`, texto com `&`/`<` e resultado vazio.
  - Aceite: a saída esperada é PDF válido, sem divisão horizontal e com linhas em continuação vertical.
  - Verificar: os testes falham porque o renderizador PDF ainda não existe.
- [ ] T009 [US1] Implementar `gerar_pdf_acompanhamento(linhas, graus_visiveis, gerado_em) -> bytes` em `contatos/relatorio_acompanhamento.py` usando ReportLab `Table`/`TableStyle` e `landscape(A4)`.
  - Aceite: dimensões de coluna ajustadas à largura disponível; datas `MM/AAAA`; cabeçalho repetido; nomes quebram em linhas; texto de usuário é escapado antes de `Paragraph`.
  - Verificar: executar testes PDF com todas as 30 colunas e com seleção parcial de Corpo.
- [ ] T010 [US1] Escrever testes RED do toolbar em `teste/test_acompanhamento_exportacao.py` para ícones SVG + rótulos Filtrar/Limpar/Relatório, menu PDF/XLSX, filtros do formulário enviados no download e ausência de `page`.
  - Aceite: teste confirma que Vale/Loja/Corpos e sort são enviados e que o menu é acessível por teclado.
  - Verificar: os testes falham antes da mudança do template.
- [ ] T011 [US1] Atualizar `contatos/templates/contatos/acompanhamento.html` com ícones HAZON em Filtrar/Limpar/Relatório e menu acessível PDF/XLSX; as ações de formato enviam os controles atuais via `formaction`/GET.
  - Aceite: os três controles mantêm texto visível, foco e responsividade; a seleção de Corpo continua aplicando imediatamente.
  - Verificar: executar testes de template/filtros e conferir navegação por teclado.

## Fase 4: Polish e validação cruzada

- [ ] T012 Rodar `teste/test_acompanhamento_exportacao.py` e `teste/test_acompanhamento_graus.py`, `manage.py check` e `makemigrations --check --dry-run`; atualizar `staticfiles`/imagem só depois de testes verdes e conferir `/healthz/`.
  - Aceite: não há migration nova; as rotas não vazam tenant; a página mantém 20 linhas; exports contêm todos os filtros.
  - Verificar: executar `docker compose up -d --build --no-deps app` e validar HTTP 200 no health check.

## Dependências e ordem

```text
T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008 → T009 → T010 → T011 → T012
```

- Há uma única história US1 (P1); não existem histórias independentes que possam ser entregues isoladamente.
- As tarefas permanecem sequenciais porque o resolver, o contrato de linhas, os renderizadores e o formulário compartilham filtros/colunas.
- Não há oportunidade segura de paralelismo sem criar conflitos no mesmo módulo de renderer e arquivo de testes.

## Exemplo de execução paralela

Não há pares de tarefas marcados `[P]`: os testes e renderizadores compartilham `teste/test_acompanhamento_exportacao.py`, `contatos/relatorio_acompanhamento.py` e o mesmo contrato de linhas. Manter a sequência indicada evita divergência entre PDF, XLSX e tabela.

## Estratégia de entrega

- **MVP:** concluir T001–T009 para gerar e validar PDF/XLSX com filtros e isolamento corretos.
- **Interface completa:** concluir T010–T011 para apresentar seleção de formato e botões com ícones/rótulos.
- **Pronto para uso local:** concluir T012, rebuild e health check.

## Critério independente de aceite de US1

- Para o mesmo estado de filtros, HTML, PDF e XLSX apresentam a mesma lista ordenada de Membros e as mesmas colunas de grau.
- Com 21 ou mais resultados e `page=2`, o arquivo continua contendo todos os resultados filtrados.
- Usuário de tenant A nunca recebe linhas do tenant B; `admin_saas` mantém somente o acesso global permitido pelo sistema.
- PDF A4 paisagem exibe todas as colunas na mesma largura e datas `MM/AAAA`; XLSX preserva datas reais com formato visual mês/ano.
