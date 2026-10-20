# Spec: Categorizar Lojas por Corpo

**Status:** Aprovada pelo usuário; implementação do Corpo, CRUD, fluxo SaaS de inclusão e Acompanhamento concluída e revisada. Filtros nas listas de Lojas e Membros seguem em `specs/008-filtros-corpo-listas/`.

## Objetivo

Cada Loja cadastrada deve ter um **Corpo**, tratado como sua categoria. O Corpo será persistido na tabela de Lojas, escolhido no cadastro e na edição, e visível na listagem e na consulta detalhada. As Lojas existentes recebem **Perfeição** na migração inicial, conforme solicitado.

## Categorias

| Valor persistido | Rótulo | Faixa de graus |
|---|---|---:|
| `perfeicao` | Perfeição | 4º–14º |
| `capitulo` | Capítulo | 15º–18º |
| `kadosh` | Kadosh | 19º–30º |
| `consistorio` | Consistório | 31º–32º |
| `sc33` | SC33 | 33º |

O Corpo é escolhido manualmente; não é calculado a partir de `Loja.numero`, que permanece como identificador da Loja. O conjunto é fechado nesta entrega: não será criada uma tabela de catálogo administrável.

## Requisitos funcionais

1. Adicionar `Loja.corpo` como campo persistido com as cinco opções acima.
2. Criar migração que atribua `Perfeição` a todas as Lojas existentes sem alterar os demais dados.
3. No formulário de inclusão, exibir seleção obrigatória de Corpo sem selecionar uma categoria silenciosamente; validar a opção no servidor.
4. No formulário de alteração, exibir o Corpo atual, permitir trocá-lo e validar a opção no servidor.
5. Exibir o Corpo como coluna na tabela/listagem de Lojas e como informação na consulta detalhada.
6. Preservar o isolamento por tenant e permissões. Permitir que `admin_saas` sem tenant selecionado abra a inclusão de Loja e escolha um Vale ativo no próprio formulário. No POST, validar o Vale ativo por allowlist e gravar a Loja no tenant desse Vale; sem Vale válido, não criar registro. Esta exceção vale apenas para incluir Loja; as demais operações mantêm suas regras atuais.
7. Na tela Acompanhamento, mudar o rótulo do grupo 15º–18º de **Rosa Cruz** para **Capítulo**. O filtro continua baseado nos graus registrados no membro; não passa a usar `Loja.corpo`. Corpos marcados também limitam as colunas de grau visíveis à união das faixas selecionadas, mantendo Membro e Presença; sem corpo marcado, mostrar 4º–33º.
8. Não adicionar filtro por Corpo na listagem de Lojas nesta entrega.

## Stack e comandos

- Django 5.2, Python 3.13, PostgreSQL, templates Django e Tailwind já existentes.
- Testes locais focados: `python -m pytest --ds=core.settings_vale_test teste/test_loja_local.py teste/test_acompanhamento_graus.py` (configurar a URL do PostgreSQL de teste local na porta 5434, como no fluxo existente).
- Verificações: `python manage.py check`, `python manage.py makemigrations --check --dry-run` e Ruff nos arquivos Python alterados.
- Container local: `docker compose up -d --build --force-recreate app`.

## Estrutura prevista

- `contatos/models.py`: opções e campo `Loja.corpo`.
- `contatos/migrations/`: migração de schema e valor inicial para dados existentes.
- `contatos/views/gprb_lojas.py`: leitura, validação e serialização do campo nos fluxos locais de Loja.
- `contatos/templates/contatos/lojas.html`: coluna Corpo.
- `contatos/templates/contatos/loja_nova.html` e `loja_editar.html`: seleção obrigatória.
- `contatos/templates/contatos/loja_detalhe.html`: exibição do Corpo.
- `contatos/views/acompanhamento.py` e seu template/testes: rótulo Capítulo, mantendo filtro por grau do membro.
- `teste/test_loja_local.py`, `teste/test_permissoes_vale_loja.py` e `teste/test_acompanhamento_graus.py`: persistência, validação, exibição, permissões e nomenclatura.

## Convenções de implementação

Manter o padrão existente de escolhas Django e validação explícita de POST. Exemplo conceitual:

```python
CORPO_CHOICES = (
    ('perfeicao', 'Perfeição'),
    ('capitulo', 'Capítulo'),
    ('kadosh', 'Kadosh'),
    ('consistorio', 'Consistório'),
    ('sc33', 'SC33'),
)
```

O formulário web exige escolha explícita. O campo do modelo usará Perfeição como valor padrão para compatibilidade com criações internas existentes que ainda não enviem `corpo`; a migração também preenche as linhas atuais com esse valor.

## Estratégia de testes

- Confirmar as cinco opções e o default de compatibilidade do modelo.
- Exercitar inclusão e edição com cada valor válido, e rejeitar Corpo ausente ou inválido no POST.
- Confirmar que a migração atribui Perfeição às Lojas existentes.
- Verificar a coluna da listagem, a informação da consulta detalhada e a seleção correta no formulário de edição.
- Reexecutar a matriz de permissões de Loja com payloads válidos contendo `corpo`.
- Verificar que a mudança de rótulo no Acompanhamento preserva as faixas 15º–18º e a filtragem por graus do membro.
- Reexecutar os testes de tenant/permissões das rotas locais de Loja e a regressão focada existente.
- Verificar inclusão SaaS sem tenant: GET oferece Vales ativos; POST com Vale válido grava sob o tenant desse Vale; Vale ausente/inativo/inválido não cria Loja.

## Limites

- **Sempre:** validar Corpo no servidor; manter o escopo de tenant; não alterar outras colunas ou dados das Lojas durante o backfill.
- **Perguntar antes:** permitir categorias administráveis, derivar Corpo de outro campo, ou usar Corpo da Loja para filtrar membros no Acompanhamento.
- **Não fazer:** criar catálogo relacional, mudar o significado de `Loja.numero`, ou reclassificar as Lojas atuais para além de Perfeição.

## Critérios de sucesso

- As cinco categorias são persistidas e exibidas com os rótulos corretos.
- Todas as Lojas existentes ficam com `corpo='perfeicao'` após a migração.
- Inclusão e edição exigem escolha válida e a consulta/listagem exibem o Corpo salvo.
- A tela Acompanhamento chama 15º–18º de Capítulo e continua filtrando pelo histórico de graus do membro.
- Testes focados, verificações Django/Ruff e build do container passam.

## Decisões confirmadas

- Campo de opções fixas, não catálogo relacional nem derivação do número.
- Seleção manual do Corpo em inclusão/edição.
- Lojas existentes: Perfeição.
- Acompanhamento: Capítulo substitui Rosa Cruz; filtro continua baseado no grau do membro.
- `admin_saas` sem tenant pode incluir Loja somente informando um Vale ativo, que define o tenant gravado.
