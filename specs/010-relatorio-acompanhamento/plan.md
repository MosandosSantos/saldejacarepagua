# Exportação do Acompanhamento — Plano de Implementação

> **Para agentes de implementação:** usar `executing-plans` para execução nativa, ou `subagent-driven-development` somente se o usuário escolher a abordagem com subagentes. Cada tarefa segue TDD.

**Objetivo:** baixar o Acompanhamento filtrado em PDF A4 paisagem e XLSX, com todas as linhas dos filtros ativos e sem vazamento de dados entre tenants.

**Arquitetura:** extrair a consulta filtrada/ordenada e a serialização das linhas para um contrato comum entre a tela e os downloads. Uma view autenticada valida o formato e chama renderizadores isolados: ReportLab para PDF e openpyxl para XLSX. O formulário oferece um menu Relatório cujas opções enviam os controles correntes via GET, sem `page`.

**Stack:** Django 5.2, Python 3.13, PostgreSQL, templates Django/Tailwind HAZON, pytest-django; ReportLab e openpyxl já são dependências do projeto.

**Spec:** `specs/010-relatorio-acompanhamento/spec.md`

## Restrições globais

- Exportar todos os Membros correspondentes aos filtros; ignorar `page`.
- Preservar Vale, Loja, Corpo/grau, ordenação e escopo de tenant da página.
- A saída tem Membro, Presença e somente as colunas de grau visíveis; não acrescentar Vale/Loja.
- PDF A4 paisagem, largura única, datas `MM/AAAA`, cabeçalho repetido e linhas em páginas verticais.
- XLSX mantém valores de data reais formatados visualmente como `MM/AAAA`; congela panes em `C2` e habilita autofiltro.
- Aceitar apenas `pdf` e `xlsx`; não persistir arquivos no servidor.
- Reusar ReportLab/openpyxl existentes; não adicionar dependências nem alterar schema.
- Filtrar, Limpar e Relatório exibem ícone SVG e texto; controles continuam acessíveis por teclado.
- O baseline conhecido da suíte completa é vermelho (`208 failed, 660 passed, 48 skipped, 13 errors`); reportar falhas pelo nome e não afirmar que a suíte completa está verde.

## Review Focus

- Um usuário muda Vale/Loja e escolhe formato sem clicar Filtrar: o arquivo precisa receber os valores correntes do formulário — teste na Tarefa 5.
- Um usuário de tenant A manipula Vale/Loja de tenant B: nenhum dado de B pode vazar — teste na Tarefa 2.
- Uma URL de página 2 deve exportar todos os resultados filtrados, não somente a página atual — testes nas Tarefas 2–4.
- Seleção múltipla de Corpos e histórico com vários graus deve manter OR, união das colunas e um único Membro por linha — teste nas Tarefas 1–2.
- Nome com `=`, `&` ou `<` não pode virar fórmula XLSX nem quebrar o PDF — testes nas Tarefas 3–4.

---

## Mapa de arquivos e responsabilidades

- `contatos/views/acompanhamento.py`: resolver uma consulta tenant-scoped, filtrada e ordenada sem paginação; montar linhas comuns para tabela e exportações.
- `contatos/views/acompanhamento_exportacao.py` (novo): validar o formato, exigir login/Vale ativo e responder com download.
- `contatos/relatorio_acompanhamento.py` (novo): renderizar bytes PDF/XLSX a partir de linhas/colunas já filtradas, sem acesso ao ORM.
- `contatos/membros_urls.py`, `contatos/views/__init__.py`: registrar/expor a nova rota.
- `contatos/templates/contatos/acompanhamento.html`: ícones com rótulos e menu de formatos que submete os filtros atuais.
- `teste/test_acompanhamento_exportacao.py` (novo): testes de query, tenant, downloads, conteúdo e segurança.
- `teste/test_acompanhamento_graus.py`: regressões da tela, filtros e colunas após extrair o caminho comum.

## Contratos entre tarefas

- `ConsultaAcompanhamento` contém `queryset` (filtrado, ordenado, sem paginação), `graus_visiveis`, grupos/graus selecionados, `ordenar` e `direcao`.
- `_resolver_consulta_acompanhamento(request, tenant_ids) -> ConsultaAcompanhamento` concentra parsing, allowlists, filtros OR, scoping e colunas visíveis.
- `_linhas_acompanhamento(membros, graus_visiveis) -> list[dict]` produz `id`, `nome`, `presenca`, `tem_presenca` e datas por grau; recebe a página na view HTML ou todos os Membros no exportador.
- `gerar_xlsx_acompanhamento(linhas, graus_visiveis, gerado_em) -> bytes`.
- `gerar_pdf_acompanhamento(linhas, graus_visiveis, gerado_em) -> bytes`.
- `acompanhamento_exportar(request, formato) -> HttpResponse` aceita `pdf`/`xlsx`, retorna MIME/disposição de anexo e nunca aplica `Paginator`.

### Task 1 — Unificar consulta e serialização sem alterar a tela

**Arquivos:** `contatos/views/acompanhamento.py`, `teste/test_acompanhamento_graus.py`.

- [ ] **Passo 1: Escrever testes RED** de consulta/linhas para filtro Vale + Loja + Corpo/grau, semântica OR, união das colunas, ordenação e uma linha por Membro.
- [ ] **Passo 2: Verificar RED** — os testes devem falhar porque o contrato de consulta/linhas compartilhado ainda não existe.
- [ ] **Passo 3: Implementar `_resolver_consulta_acompanhamento(request, tenant_ids)`** — extrair o filtro e a ordenação atuais para `ConsultaAcompanhamento`; retornar QuerySet ordenado, graus visíveis e estado normalizado; nunca paginar dentro do helper.
- [ ] **Passo 4: Implementar `_linhas_acompanhamento(membros, graus_visiveis)`** — centralizar busca em lote de presença e criação dos campos de cada linha; a tabela passa somente os 20 membros da página.
- [ ] **Passo 5: Verificar GREEN** — todos os testes de `teste/test_acompanhamento_graus.py` continuam passando e `Paginator` permanece com 20 linhas na resposta HTML.

### Task 2 — Criar endpoint de exportação tenant-scoped

**Arquivos:** criar `contatos/views/acompanhamento_exportacao.py`; alterar `contatos/membros_urls.py`, `contatos/views/__init__.py`; criar `teste/test_acompanhamento_exportacao.py`.

- [ ] **Passo 1: Escrever testes RED** para formatos permitidos/desconhecidos, usuário sem Vale ativo, tenant A/B, filtros combinados, ordenação e mais de 20 linhas.
- [ ] **Passo 2: Verificar RED** — as rotas/formatos ainda não existem.
- [ ] **Passo 3: Registrar `acompanhamento/relatorio/<str:formato>/`** antes das rotas dinâmicas em `contatos/membros_urls.py` e expor a view em `contatos/views/__init__.py`.
- [ ] **Passo 4: Implementar `acompanhamento_exportar(request, formato)`** — exigir login e Vale ativo, restringir formato a `pdf|xlsx`, chamar o helper da Tarefa 1, ignorar `page` e obter todas as linhas filtradas.
- [ ] **Passo 5: Definir download em memória** — MIME correto, filename `acompanhamento-YYYY-MM-DD.<ext>`, `Content-Disposition: attachment`, e saída válida sem linhas.
- [ ] **Passo 6: Verificar GREEN** — confirmar filtros, ordenação, acesso, headers e exportação de registros além da página 1.

### Task 3 — Implementar XLSX

**Arquivos:** criar/alterar `contatos/relatorio_acompanhamento.py`; `teste/test_acompanhamento_exportacao.py`.

- [ ] **Passo 1: Escrever testes RED** para workbook legível por openpyxl, aba `Acompanhamento`, colunas, todas as linhas, datas `MM/AAAA`, autofiltro, `freeze_panes == 'C2'` e arquivo vazio.
- [ ] **Passo 2: Escrever teste de fórmula** — nome começando com `=` deve ser texto, nunca fórmula (`cell.data_type != 'f'`).
- [ ] **Passo 3: Implementar `gerar_xlsx_acompanhamento(...)`** — montar workbook em `BytesIO`; escrever datas como valores date com formato `mm/yyyy`; congelar cabeçalho e colunas Membro/Presença; definir autofiltro/larguras.
- [ ] **Passo 4: Verificar GREEN** — abrir a resposta real com openpyxl e confirmar células, formato, filtros e texto seguro.

### Task 4 — Implementar PDF A4 paisagem

**Arquivos:** `contatos/relatorio_acompanhamento.py`; `teste/test_acompanhamento_exportacao.py`.

- [ ] **Passo 1: Escrever testes RED** para assinatura `%PDF-`, MIME, nome, A4 paisagem, grid, repetição do cabeçalho, data mês/ano e estado vazio.
- [ ] **Passo 2: Implementar `gerar_pdf_acompanhamento(...)`** com ReportLab `SimpleDocTemplate`, `landscape(A4)`, `Table`/`TableStyle`, margens compactas e `repeatRows=1`.
- [ ] **Passo 3: Manter largura única** — reservar colunas Membro/Presença, distribuir o restante entre graus visíveis, usar tipografia compacta e permitir que nomes quebrem em linhas; nenhuma quebra horizontal.
- [ ] **Passo 4: Formatar/sanitizar texto** — datas como `MM/AAAA`; escapar texto usado em `Paragraph`; datas ausentes como `—`.
- [ ] **Passo 5: Verificar GREEN** com 30 graus, filtros de um/múltiplos Corpos, mais de uma página vertical e texto contendo `&`/`<`.

### Task 5 — Integrar botões, ícones e menu de formatos

**Arquivos:** `contatos/templates/contatos/acompanhamento.html`; `teste/test_acompanhamento_exportacao.py`.

- [ ] **Passo 1: Escrever testes RED de interface** — ícone SVG e rótulo visível em Filtrar/Limpar/Relatório; opções PDF/XLSX; envio dos filtros atuais; ausência de `page` no download.
- [ ] **Passo 2: Implementar menu Relatório acessível** — manter o formulário GET; opções PDF/XLSX usam `formaction` para a nova rota e enviam Vale/Loja/Corpos atualmente selecionados.
- [ ] **Passo 3: Preservar parâmetros sem controle visível** — enviar `ordenar`, `direcao` e todos os valores `grau` como inputs ocultos quando presentes; nunca enviar `page`.
- [ ] **Passo 4: Adicionar ícones HAZON** — SVG inline de funil, limpar e relatório/download; ícones decorativos `aria-hidden`, textos permanecem acessíveis e visíveis; menu navegável por teclado.
- [ ] **Passo 5: Verificar GREEN/responsividade** — desktop e viewport estreito, menu aberto, foco visível, form submit dos formatos e filtros.

### Task 6 — Regressão final e app local

**Arquivos:** somente correções necessárias nas tarefas anteriores.

- [ ] Rodar `teste/test_acompanhamento_exportacao.py` e `teste/test_acompanhamento_graus.py` com `VALE_TEST_DATABASE_URL` no PostgreSQL local de testes.
- [ ] Rodar `manage.py check` e `makemigrations --check --dry-run`; nenhuma migration deve ser criada.
- [ ] Rodar detector Impeccable no template e corrigir findings não intencionais.
- [ ] Rebuild local: `docker compose up -d --build --no-deps app`; confirmar `/healthz/` HTTP 200.
- [ ] Executar `pytest teste/`; reportar falhas pelo nome, considerando o baseline atual `208 failed, 660 passed, 48 skipped, 13 errors`.

## Verificação do plano

- Cada requisito da spec tem pelo menos uma tarefa: filtros/tenant em T1–T2, XLSX em T3, PDF em T4, interface em T5 e regressão em T6.
- As duas saídas consomem o mesmo contrato de consulta/linhas; não há duplicação de filtros.
- Não há mudança de schema, dependência ou armazenamento persistente de arquivos.
