# Spec: Paginação e Relatórios da Lista de Lojas

**Status:** execução autônoma autorizada pelo usuário; decisões e suposições ficam registradas para revisão.

## Objetivo

Facilitar a navegação da lista `/contatos/lojas/` com 20 lojas por página e permitir baixar um relatório PDF A4 paisagem ou Excel (.xlsx) das lojas filtradas.

## Requisitos

1. A lista HTML pagina em grupos de 20, ordenados por nome e ID.
2. As páginas seguinte/anterior preservam `q` e os filtros `corpo`; o contador mostra o total filtrado, não apenas a página corrente.
3. Adicionar botão **Relatório** próximo dos filtros, com opções PDF e Excel (.xlsx), seguindo o menu do Acompanhamento.
4. Os arquivos usam os filtros correntes `q` e `corpo`, a ordenação padrão da lista e o escopo de tenant autorizado no servidor.
5. A exportação inclui **todas** as lojas que correspondem aos filtros, ignora `page` e não exporta uma página parcial.
6. Colunas de dados exportadas, sem controles de expansão nem ações: Loja, Corpo, Vale, Presidente, Celular do presidente, Membros e Situação.
7. PDF em A4 paisagem, todas as colunas na mesma largura de página, cabeçalho repetido em páginas verticais e arquivo produzido em memória.
8. XLSX com cabeçalho, autofiltro e valores textuais protegidos contra fórmula acidental. Resultado vazio ainda gera arquivo com cabeçalhos.
9. Somente `pdf` e `xlsx` são aceitos; formato desconhecido retorna 400; login/Vale/tenant seguem as proteções da lista.

## Consulta compartilhada

A listagem e os dois formatos usam o mesmo helper de filtro e ordenação para impedir divergência de resultados. A paginação é aplicada apenas à resposta HTML; o endpoint de exportação consome o QuerySet completo filtrado.

## Stack e limites

- Django 5.2, Python 3.13, templates Django/Tailwind HAZON e pytest-django.
- Reutilizar ReportLab e openpyxl existentes; nenhuma dependência, modelo ou migration nova.
- Não adicionar CSV, filtros novos, colunas privadas ou dados de contato além das colunas visíveis especificadas.
- A lista de membros expandida e seus percentuais continuam carregando via `membros-json`; paginação/exportação só alteram a listagem de Lojas.

## Arquitetura e arquivos

- `contatos/views/gprb_lojas.py`: extrair consulta tenant-scoped compartilhada; aplicar `Paginator(..., 20)` à view HTML; endpoint autenticado de exportação.
- `contatos/relatorio_lojas.py` (novo): renderizadores XLSX/PDF que recebem linhas já filtradas/formatadas e não fazem consultas próprias.
- `contatos/urls.py` e `contatos/views/__init__.py`: registrar e exportar `lojas_exportar`.
- `contatos/templates/contatos/lojas.html`: menu Relatório e navegação da paginação com preservação de filtros.
- `teste/test_lojas_paginacao_exportacao.py` (novo): página, filtros, downloads, conteúdo, tenant e casos vazios/inválidos.

## Estratégia de testes

- Mais de 20 lojas: página 1/2 contém 20/1, contador total e URLs de paginação preservam query/corpos.
- PDF/XLSX: formato, cabeçalhos, conteúdo filtrado, todos os resultados mesmo com `page=2`, A4 paisagem e conteúdo vazio.
- Tenant A não recebe lojas do tenant B por lista nem por exportação; IDs adulterados não ampliam escopo.
- Menu Relatório contém rótulos PDF/Excel e submete os filtros atuais.

## Decisões autônomas para revisão

- Relatório reproduz as colunas de dados da tabela atual; ignora o botão de expandir e os ícones de ações.
- Os filtros inválidos de `corpo` mantêm o comportamento atual de resultado vazio, inclusive em exportações.
- Nome de arquivo: `lojas-YYYY-MM-DD.pdf` / `.xlsx`; aba XLSX: `Lojas`.

## Critérios de sucesso

1. Usuário percorre todas as lojas em páginas de 20 sem perder filtros.
2. O botão Relatório oferece PDF e XLSX; ambos incluem todas as lojas filtradas, não só a página atual.
3. PDF cabe em A4 paisagem sem quebra horizontal e XLSX abre com os cabeçalhos e o autofiltro corretos.
4. Lista e relatórios permanecem isolados por tenant e a lista de membros expandida continua funcional.
