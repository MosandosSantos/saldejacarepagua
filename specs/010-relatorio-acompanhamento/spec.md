# Spec: Exportação do Acompanhamento de Membros

## Objetivo

Permitir que um usuário autenticado baixe os resultados da página `/membros/acompanhamento/` em PDF ou XLSX. Os arquivos devem respeitar os filtros e a ordenação aplicados, conter todos os resultados correspondentes (não apenas a página atual de 20 linhas) e manter o mesmo escopo autorizado por tenant da página.

### História de usuário — US1 (P1)

Como usuário do Acompanhamento, quero escolher PDF ou XLSX e baixar o relatório filtrado para imprimir ou analisar os graus e a presença dos membros.

**Aceite:** os dois formatos contêm os mesmos membros, na mesma ordem, com as mesmas colunas visíveis na tabela; os filtros e o escopo de tenant são respeitados; o PDF fica em paisagem e todas as colunas cabem na mesma largura de página.

## Regras funcionais

1. A página oferece uma ação **Relatório** com escolha explícita entre **PDF** e **XLSX**.
2. **Filtrar**, **Limpar** e **Relatório** exibem ícone SVG coerente com a ação e texto visível. Ícones não substituem os rótulos; os controles permanecem acessíveis por teclado e leitor de tela.
3. A exportação recebe os valores atuais dos filtros Vale, Loja, Corpo/grau e a ordenação. O parâmetro `page` é ignorado: exportar significa todos os Membros que satisfazem os filtros, não apenas os 20 da página atual.
4. A implementação compartilha o mesmo construtor de consulta/resultado entre a página e os exportadores. Não duplicar a lógica dos filtros em cada formato.
5. O escopo é resolvido no servidor conforme a sessão e o papel do usuário. Usuários comuns só exportam o próprio tenant; `admin_saas` conserva o acesso global que já existe na página. IDs de Vale/Loja na query string são validados dentro desse escopo.
6. A seleção de Corpo continua usando a semântica OR vigente para membros; as colunas exportadas são a união dos graus dos Corpos selecionados. Sem Corpo selecionado, exportar os graus 4º–33º.
7. Os filtros de Loja e Vale limitam os registros, mas não adicionam colunas Vale/Loja ao relatório, pois essas colunas não existem na tabela atual.
8. A ordenação vigente da tela (`ordenar`, `direcao`) é preservada nos arquivos.
9. Formato desconhecido deve ser rejeitado sem gerar arquivo. Um conjunto vazio ainda produz um arquivo válido com cabeçalho e estado sem resultados.

## Conteúdo e formato dos arquivos

### Colunas

Na ordem:

1. Membro
2. Presença (percentual ou `—` quando não há chamadas registradas)
3. Uma coluna de data para cada grau visível na tela, na ordem crescente do grau

Não incluir filtros como colunas nem usar a página atual como limite de linhas.

### PDF

- MIME type `application/pdf`; resposta como anexo para download.
- Página **A4 em paisagem**.
- Todas as colunas do relatório ficam dentro da largura de uma página; não dividir a tabela horizontalmente em páginas distintas.
- As linhas continuam verticalmente em quantas páginas forem necessárias. Repetir o cabeçalho da tabela em cada página e evitar dividir uma linha entre páginas.
- Exibir datas de grau no formato `MM/AAAA`, sem o dia.
- Usar layout tabular com linhas e colunas visíveis, título “Acompanhamento de Membros” e data de geração. Ajustar larguras e tipografia para caber a faixa completa 4º–33º; nomes podem quebrar em mais de uma linha em vez de alargar a tabela.
- Se não houver Membros, manter título e cabeçalho e exibir uma linha “Nenhum membro encontrado para esses filtros.”

### XLSX

- MIME type oficial XLSX; nome do arquivo com extensão `.xlsx`.
- Uma planilha chamada `Acompanhamento`, com as mesmas colunas, linhas, ordem e escopo do PDF.
- Incluir todos os registros filtrados, sem paginação.
- Datas são células de data reais, formatadas visualmente como `MM/AAAA`, preservando ordenação e operações do Excel.
- Cabeçalho destacado, autofiltro habilitado e painéis congelados em `C2` (cabeçalho e colunas Membro/Presença fixos durante rolagem).
- Texto vindo de nomes não pode ser interpretado como fórmula de planilha.
- Com resultado vazio, entregar planilha válida apenas com cabeçalho.

## Interface e fluxo

- Inserir **Relatório** no grupo de ações junto de **Filtrar** e **Limpar**, com ícone e rótulo em cada ação.
- Ao ativar Relatório, abrir um menu acessível contendo as opções PDF e XLSX. A escolha submete os filtros atualmente preenchidos no formulário e inicia o download.
- Os checkboxes de Corpo continuam aplicando a seleção imediatamente; Vale/Loja continuam podendo ser filtrados pelo botão Filtrar.
- Preservar a hierarquia visual HAZON, o layout responsivo e as affordances existentes da página.

## Arquitetura e arquivos

- `contatos/views/acompanhamento.py`: manter uma única resolução de filtros, escopo, colunas visíveis e ordenação que possa ser reutilizada pela página e pela exportação; a paginação fica somente na resposta HTML.
- `contatos/views/acompanhamento_exportacao.py` (novo): validar formato, obter o resultado filtrado sem paginação e entregar a resposta de download.
- `contatos/relatorio_acompanhamento.py` (novo): renderizadores PDF e XLSX que recebem dados já filtrados/normalizados; não fazem suas próprias consultas tenant-scoped.
- `contatos/membros_urls.py` e `contatos/views/__init__.py`: registrar e expor a rota autenticada de exportação.
- `contatos/templates/contatos/acompanhamento.html`: menu Relatório e ícones com rótulos nos três botões.
- `teste/test_acompanhamento_exportacao.py` (novo) e `teste/test_acompanhamento_graus.py`: testes de arquivos, filtros, escopo, colunas e layout.

## Stack e dependências

- Django 5.2, Python 3.13, PostgreSQL, templates Django e Tailwind HAZON.
- Gerar PDF com **ReportLab**, já presente em `requirements.txt`.
- Gerar XLSX com **openpyxl**, já presente em `requirements.txt`.
- Não adicionar dependências novas nem alterar schema/modelos para exportar.

## Comandos de validação

Executar no PowerShell com `VALE_TEST_DATABASE_URL` apontando para o PostgreSQL local de testes (`127.0.0.1:5434`):

```powershell
.\.venv\Scripts\python.exe -m pytest teste/test_acompanhamento_exportacao.py teste/test_acompanhamento_graus.py --ds=core.settings_vale_test -q
docker exec gprbr-app python manage.py check
docker exec gprbr-app python manage.py makemigrations --check --dry-run
docker compose up -d --build --no-deps app
```

## Estratégia de testes

- Testar o construtor de dados compartilhado com filtros combinados de Vale, Loja e Corpo/grau; verificar OR dos Corpos, colunas visíveis e ordenação.
- Criar mais de 20 membros elegíveis e comprovar que PDF e XLSX exportam todos, independentemente de `page`.
- Testar dois tenants: membro/dado do tenant B nunca aparece para usuário comum do tenant A; testar também Vale/Loja adulterados e papel global autorizado.
- PDF: status, Content-Type, Content-Disposition, assinatura `%PDF-`, paisagem A4, cabeçalho repetido e conteúdo de datas `MM/AAAA`.
- XLSX: abrir os bytes com openpyxl, validar aba/cabeçalhos/linhas, filtros, congelamento `C2`, formatação de mês/ano e texto seguro contra fórmula.
- Formato inválido não gera arquivo; resultado vazio gera ambos os arquivos com cabeçalho e estado vazio.
- Template: três ações têm SVG e nome visível; menu de formatos é navegável por teclado e envia os filtros correntes sem `page`.

## Limites

- **Sempre:** respeitar os filtros, a ordenação e o escopo de tenant da página; ignorar somente a paginação; manter os dados de presença e os graus conforme a tabela atual; gerar PDF em A4 paisagem sem quebra horizontal.
- **Não fazer:** exportar dados de tenants fora do escopo; exportar somente 20 linhas; adicionar colunas não visíveis; persistir arquivos no servidor; adicionar dependências; mudar regras de filtro.
- **Perguntar antes:** adicionar CSV/outros formatos, incluir colunas Vale/Loja, alterar o tamanho de papel/orientação, remover a coluna Presença ou mudar o conjunto de graus.

## Critérios de sucesso

1. O usuário escolhe PDF ou XLSX no menu Relatório; os três controles Filtrar/Limpar/Relatório têm ícone SVG e texto.
2. Cada formato exporta todos os registros filtrados, com as mesmas colunas visíveis e ordenação da tela, ignorando `page`.
3. O PDF é A4 paisagem, sem divisão horizontal, mostra datas `MM/AAAA` e repete cabeçalhos ao continuar verticalmente.
4. O XLSX tem uma planilha filtrável, cabeçalho/painéis congelados e datas reais formatadas em mês/ano.
5. Nenhum relatório vaza dados entre tenants; os relatórios respeitam o papel e os filtros Vale/Loja/Corpo/grau.
6. Relatórios vazios e formatos inválidos são tratados de forma previsível e coberta por testes.
