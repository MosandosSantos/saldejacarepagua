# Paginação e Relatórios de Lojas — Plano

> **Para execução autônoma neste workspace:** REQUIRED SUB-SKILL: `executing-plans`; o usuário pediu escolhas sem novas perguntas. Sem subagentes, commits, push ou deploy.

**Objetivo:** paginar `/contatos/lojas/` em 20 lojas e exportar todas as lojas filtradas em PDF A4 paisagem ou XLSX.

**Arquitetura:** um construtor tenant-scoped compartilhado aplica busca e filtros; a view HTML pagina esse QuerySet em 20; uma view de relatório consome o mesmo QuerySet sem paginação e chama renderizadores em memória para PDF/XLSX. A tabela de UI acrescenta menu Relatório e controles de página preservando filtros.

**Tech Stack:** Django 5.2, Python 3.13, PostgreSQL, templates Django/Tailwind, ReportLab, openpyxl e pytest-django.

**Spec:** `specs/012-lojas-paginacao-relatorio/spec.md`

## Global Constraints

- Página HTML: exatamente 20 lojas por página, ordenação nome/ID, filtros `q` e `corpo` preservados nas URLs de página.
- Exportações: todos os resultados dos filtros ativos; `page` é ignorado; mesmos resultados/ordem da lista sem controles de UI.
- Colunas: Loja, Corpo, Vale, Presidente, Celular do presidente, Membros, Situação.
- PDF A4 landscape, largura única, cabeçalho repetido nas páginas verticais.
- XLSX em memória, autofiltro, texto seguro; usar dependências existentes.
- Tenant resolve no servidor com `_lojas_visiveis`; query string nunca altera escopo.
- Nenhuma alteração a `membros-json`, percentuais, modelos, migrations ou dependências.

## Review Focus

- Usuário vai à página 2 depois de filtrar por nome e por mais de um Corpo: query e contador continuam corretos.
- Exportação feita em `page=2` ainda inclui todos os filtros, mas todos os registros filtrados.
- Vale/loja adulterados não vazam dados cross-tenant.
- Lojas sem Vale ou sem presidente mantêm valores de fallback (`—`) e não quebram PDF/XLSX.
- Resultado vazio gera arquivo válido com cabeçalho e página sem lojas.

---

## Interfaces

- Task 1 produz `_consulta_lojas_filtradas(request) -> ConsultaLojas`, com `queryset` filtrado e ordenado, `termo`, `corpos_requisitados`, `corpos_filtro` e `vale`.
- Task 2 consome o mesmo helper; produz `lojas_exportar(request, formato) -> HttpResponse` e renderizadores `gerar_xlsx_lojas(linhas, gerado_em) -> bytes` / `gerar_pdf_lojas(linhas, gerado_em) -> bytes`.
- Task 3 consome `page_obj`, `pagination_urls`, filtros atuais e URLs de exportação na interface.

### Task 1: Consulta compartilhada e paginação HTML

**Files:** modificar `contatos/views/gprb_lojas.py`; criar `teste/test_lojas_paginacao_exportacao.py`.

- [x] RED: teste `test_lista_lojas_pagina_em_vinte_preservando_filtros` com 21 lojas, múltiplos corpos e busca; esperar 20/1, total filtrado e URLs preservadas.
- [x] Cobrir por caracterização que Corpo inválido retorna zero resultados sem ampliar a consulta (a allowlist já existia antes desta mudança).
- [x] GREEN: extrair `_consulta_lojas_filtradas(request)` a partir de `_lojas_visiveis`; ordenar por `nome, pk` e aplicar `Paginator(queryset, 20).get_page(page)` apenas à listagem HTML.
- [x] Contexto inclui `page_obj`, total filtrado, filtros selecionados e URLs anterior/próxima derivadas de `request.GET`.
- [x] Rodar os testes da listagem e verificar 20 por página e preservação de filtros.

### Task 2: Renderizadores e endpoint tenant-scoped

**Files:** criar `contatos/relatorio_lojas.py`; modificar `contatos/views/gprb_lojas.py`, `contatos/urls.py`, `contatos/views/__init__.py`; estender testes.

- [x] RED: testar PDF/XLSX, formato desconhecido, Vale inativo, tenant A/B, 21+ linhas com `page=2`, todos os cabeçalhos e resultado vazio.
- [x] GREEN: implementar `gerar_xlsx_lojas(linhas, gerado_em)` com openpyxl; células textuais seguras, valores numéricos e autofiltro na aba `Lojas`.
- [x] GREEN: implementar `gerar_pdf_lojas(linhas, gerado_em)` com ReportLab `landscape(A4)`, largura total única, `repeatRows=1` e quebra somente vertical.
- [x] Implementar `lojas_exportar(request, formato)` com login, Vale ativo, allowlist `pdf|xlsx`, consulta compartilhada sem Paginator e headers de download.
- [x] Registrar rota `lojas/relatorio/<str:formato>/` e executar os testes; ambos os formatos devem incluir todas as lojas filtradas.

### Task 3: Menu de relatório e controles de página

**Files:** modificar `contatos/templates/contatos/lojas.html`; estender `teste/test_lojas_paginacao_exportacao.py`.

- [x] RED: testar menu Relatório com rótulos PDF/Excel e `formaction`s; confirmar que filtros correntes são submetidos e `page` não é usado como limite do relatório.
- [x] GREEN: adicionar botão Relatório no formulário existente com menu acessível de PDF e Excel; opções usam GET e exportam sem `page`.
- [x] Adicionar navegação anterior/próxima e “Página X de Y” abaixo da tabela; links mantêm `q` e todos os `corpo` selecionados; estado vazio continua com `colspan=9`.
- [x] Rodar detector Impeccable uma vez no template alterado; corrigir somente achados mecânicos introduzidos nesta alteração.

### Task 4: Verificação local e handoff

- [x] Rodar todos os testes focados de lojas e o conjunto de testes de Iniciação Grau 9.
- [x] Rodar Ruff, `manage.py check` e `makemigrations --check --dry-run`.
- [x] Rebuild Docker e confirmar `/healthz/` HTTP 200.
- [x] Rodar a suíte completa uma vez depois das duas alterações; resultado `211 failed, 663 passed, 48 skipped, 37 errors`; confirmar que os módulos de teste novos/de regressão desta feature não estão entre falhas/erros.
- [x] Deixar documentação e workspace sem commit para revisão do usuário; sem push ou deploy.
