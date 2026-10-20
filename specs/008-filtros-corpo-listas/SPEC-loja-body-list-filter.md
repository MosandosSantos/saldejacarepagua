# Spec: Filtro por Corpo na Lista de Lojas

**Module id:** `loja-body-list-filter`  
**Status:** Aprovada pelo usuário; implementada e revisada. A lista de Membros é especificada separadamente no módulo `member-body-list-filter`.

## Objetivo

Permitir filtrar a listagem de Lojas pelo campo `Loja.corpo`, para localizar rapidamente as Lojas de Perfeição, Capítulo, Kadosh, Consistório ou SC33. O filtro complementa a busca textual existente e respeita o escopo de tenant já aplicado à listagem.

## Categorias e parâmetros

Reutilizar os cinco valores persistidos de `Loja.corpo`:

| Valor GET repetível (`corpo`) | Rótulo |
|---|---|
| `perfeicao` | Perfeição |
| `capitulo` | Capítulo |
| `kadosh` | Kadosh |
| `consistorio` | Consistório |
| `sc33` | SC33 |

Uma seleção pode conter vários parâmetros `corpo`; não há checkbox “Todos”. Nenhum corpo selecionado significa não filtrar por categoria.

## Requisitos funcionais

1. Exibir na lista de Lojas checkboxes acessíveis para as cinco categorias existentes.
2. Ao marcar ou desmarcar uma categoria, aplicar o filtro imediatamente via GET, mantendo o termo de busca `q` e os corpos selecionados.
3. Corpos selecionados combinam por união (**OR**): a Loja aparece quando seu único `corpo` pertence a qualquer valor selecionado.
4. A busca textual existente e o filtro de Corpo combinam por interseção (**AND**); os campos atuais cobertos por `q` não mudam.
5. Com nenhum Corpo selecionado, manter o comportamento atual da lista, incluindo a busca textual quando `q` estiver preenchido.
6. Valor de Corpo não reconhecido não deve ampliar resultados; retornar lista vazia para esse filtro inválido.
7. Preservar isolamento de tenant, permissões, ordem atual da lista, coluna Corpo já existente e ações atuais.
8. A seleção permanece marcada após a navegação GET. Não adicionar categoria “Todos”; limpar corpos é possível desmarcando as caixas.

## Stack, comandos e estrutura

- Django 5.2, Python 3.13, PostgreSQL, templates Django e Tailwind existentes.
- Teste local: `.venv\Scripts\python.exe -m pytest --ds=core.settings_vale_test teste/test_loja_local.py -k corpo -q` com `VALE_TEST_DATABASE_URL` apontando ao PostgreSQL de teste em `127.0.0.1:5434`.
- Verificações: `python manage.py check`, `python manage.py makemigrations --check --dry-run` e Ruff nos arquivos Python alterados.
- Build/runtime local: `docker compose up -d --build --force-recreate app`.
- Arquivos previstos: `contatos/views/gprb_lojas.py`, `contatos/templates/contatos/lojas.html` e testes em `teste/test_loja_local.py`.

## Convenções de implementação

Manter a consulta local existente e filtrar por allowlist antes de compor o queryset:

```python
corpos = request.GET.getlist('corpo')
if any(corpo not in dict(Loja.CORPO_CHOICES) for corpo in corpos):
    qs = qs.none()
elif corpos:
    qs = qs.filter(corpo__in=corpos)
```

O formulário preserva `q`; os checkboxes usam os mesmos valores do modelo e submetem ao mudar, sem JavaScript que altere a semântica do GET.

## Estratégia de testes

- Cobrir cada corpo válido e confirmar que outros corpos não aparecem.
- Cobrir união de múltiplos corpos sem duplicar Lojas.
- Cobrir combinação AND entre Corpo e busca textual.
- Cobrir nenhum Corpo selecionado, query preservada e seleção marcada após GET.
- Cobrir valor desconhecido retornando zero resultados.
- Reexecutar os testes atuais de isolamento por tenant e permissões de Loja; não mudar suas regras.

## Limites

- **Sempre:** consultar `Loja` com o queryset tenant-scoped de `_lojas_visiveis`; validar os códigos de Corpo contra `Loja.CORPO_CHOICES`.
- **Perguntar antes:** adicionar filtro por Corpo em outras páginas, mudar a busca textual, adicionar “Todos” ou introduzir valores de categoria novos.
- **Não fazer:** alterar inclusão/edição/detalhe, a tabela de Membros ou os filtros da página Acompanhamento neste módulo.

## Critérios de sucesso

- Os cinco corpos filtram a lista corretamente; seleção múltipla produz OR e combina com `q` por AND.
- Nenhum Corpo marcado mantém todos os resultados permitidos pelo tenant e por `q`.
- Checkbox selecionado persiste no GET, e filtro inválido não retorna Lojas.
- Testes focados, Django checks e Ruff passam sem mudança de migrations.

## Decisões confirmadas

- Filtro direto por `Loja.corpo`.
- Cinco categorias existentes, sem checkbox “Todos”; seleção vazia não filtra.
- Aplicação imediata, OR entre corpos e AND com busca.
- Nenhuma alteração ao filtro de Membros ou Acompanhamento nesta capacidade.
