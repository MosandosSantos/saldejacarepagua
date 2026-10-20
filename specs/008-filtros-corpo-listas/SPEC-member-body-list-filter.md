# Spec: Filtro por Corpo na Lista de Membros

**Module id:** `member-body-list-filter`  
**Status:** Aprovada pelo usuário; implementada e revisada.

## Objetivo

Permitir localizar Membros pela categoria Corpo das Lojas às quais estão vinculados. Esta lista usa a relação Membro–Loja e o campo persistido `Loja.corpo`; não usa o histórico de graus do membro, que continua sendo a fonte do filtro da tela Acompanhamento.

## Categorias e parâmetros

Reutilizar os valores já aceitos pela lista de Lojas, enviados como parâmetros GET repetidos `corpo`:

| Valor | Rótulo | Faixa |
|---|---|---:|
| `perfeicao` | Perfeição | 4º–14º |
| `capitulo` | Capítulo | 15º–18º |
| `kadosh` | Kadosh | 19º–30º |
| `consistorio` | Consistório | 31º–32º |
| `sc33` | SC33 | 33º |

Não há checkbox “Todos”. Sem corpo marcado, não acrescentar filtro por Corpo; os demais filtros existentes continuam ativos.

## Requisitos funcionais

1. Exibir checkboxes acessíveis para os cinco corpos na lista de Membros (`/contatos/`).
2. Ao marcar/desmarcar um corpo, aplicar imediatamente o GET e preservar a busca e todos os demais filtros selecionados.
3. Corpos marcados combinam por união (**OR**): um Membro aparece quando possui ao menos uma Loja vinculada, do mesmo tenant, cujo `corpo` está entre os valores selecionados.
4. O filtro por Corpo combina por interseção (**AND**) com `q`, Situação, Vale, Loja, UF, Cidade e Anuidade existentes. Se uma Loja específica e um Corpo estiverem selecionados, é necessário que essa mesma Loja pertença ao Corpo escolhido.
5. Um Membro vinculado a várias Lojas que correspondam ao filtro aparece uma única vez. Membros sem Loja de corpo selecionado não aparecem quando o filtro está ativo.
6. Nenhum corpo marcado mantém a lista atual, sem restrição por Corpo.
7. Valores de Corpo desconhecidos retornam zero resultados, sem ampliar o queryset.
8. Manter o escopo de tenant do Membro e garantir que Loja de outro tenant não seja usada para satisfazer o filtro, inclusive para `admin_saas` global.
9. Acompanhamento continua filtrando e mostrando colunas de acordo com os graus registrados no Membro; esta mudança é só para a lista geral de Membros.

## Stack, comandos e estrutura

- Django 5.2, Python 3.13, PostgreSQL, templates Django e Tailwind existentes.
- Testes locais: `.venv\Scripts\python.exe -m pytest --ds=core.settings_vale_test teste/test_membro_local.py -k corpo -q` com `VALE_TEST_DATABASE_URL` apontando ao PostgreSQL de teste em `127.0.0.1:5434`.
- Verificações: `python manage.py check`, `python manage.py makemigrations --check --dry-run` e Ruff nos arquivos Python alterados.
- Build/runtime local: `docker compose up -d --build --force-recreate app`.
- Arquivos previstos: `contatos/views/crud.py` (view da rota `/contatos/`), `contatos/templates/contatos/lista.html` e testes em `teste/test_membro_local.py`.

## Convenções de implementação

Manter o queryset tenant-scoped existente. Quando corpos estiverem marcados, filtrar a relação Membro–Loja por `lojas__corpo__in=...`, restringir a Loja ao mesmo tenant do Membro e aplicar `.distinct()` para evitar duplicatas.

O form de GET da lista contém `q`, filtros atuais e checkboxes de Corpo; a mudança em um checkbox submete esse mesmo form, para que os valores selecionados permaneçam juntos na URL.

## Estratégia de testes

- Cada corpo retorna Membros com Loja correspondente e exclui Membros com apenas Lojas de outros corpos.
- Vários corpos usam OR e nunca duplicam Membros com várias Lojas correspondentes.
- Corpo e cada filtro existente (principalmente `loja` e `q`) combinam por AND.
- Loja específica e Corpo devem corresponder à mesma relação Loja–Membro.
- Vínculo a Loja de outro tenant não satisfaz o filtro.
- Sem corpo selecionado, a lista atual permanece inalterada; corpo inválido retorna zero resultados.
- GET mantém as caixas selecionadas, demais parâmetros e escopo de tenant.

## Limites

- **Sempre:** filtrar pela categoria persistida em Lojas vinculadas e respeitar o tenant de ambas as entidades.
- **Perguntar antes:** usar graus registrados do Membro como fonte, incluir Lojas de outros tenants, ou alterar Acompanhamento.
- **Não fazer:** mudar o modelo, as relações Membro–Loja, CRUD de Loja, ordenação ou as faixas de Corpo.

## Critérios de sucesso

- Os cinco corpos filtram membros por Lojas vinculadas e por mesmo tenant.
- OR entre corpos e AND com os filtros atuais funcionam sem duplicar membros.
- Nenhuma seleção deixa a lista sem filtro por Corpo; valores desconhecidos não ampliam resultados.
- Seleção GET persiste e os checkboxes aplicam imediatamente.
- Testes focados, Django checks, Ruff e build do container passam.

## Decisões confirmadas

- Fonte do filtro de Membros: `Loja.corpo` das Lojas vinculadas, não graus do Membro.
- Um membro com várias Lojas corresponde se qualquer Loja do mesmo tenant corresponder.
- Os corpos combinam por OR; todos os outros filtros existentes combinam por AND.
- Os checkboxes repetem as cinco categorias sem opção “Todos”; seleção vazia significa todos os membros permitidos pelos demais filtros.
