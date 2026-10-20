# Spec: Acompanhamento de Membros e Histórico de Graus

**Status:** aprovada e implementada parcialmente; revisar a suite completa/CI antes de merge ou deploy.

## Objetivo

Disponibilizar, no menu principal, uma página **Acompanhamento** para consultar membros, seus Vales e Lojas, datas de obtenção dos graus do 4º ao 33º e percentual de presença. A tela deve facilitar acompanhamento operacional sem armazenar datas de grau em colunas fixas do membro.

## Decisão de arquitetura

Usar a tabela auxiliar já existente `contatos.GrauMembro`, relacionada a `Membro` e ao catálogo `Grau`. Cada linha representa um grau obtido por um membro e contém sua data. A restrição existente de unicidade `(membro, grau)` será preservada; a validação da aplicação e do banco limitará o catálogo aos graus 4–33.

Não adicionar uma coluna por grau ao modelo `Membro`: isso criaria 30 campos fixos, espalharia dados repetidos e tornaria mudanças do catálogo difíceis. Não criar uma segunda tabela de histórico, porque `GrauMembro` já atende ao relacionamento e à data.

## Requisitos funcionais

### RF-1 — Histórico de graus

- A edição do membro deve permitir incluir, editar e remover várias linhas de histórico, cada uma com **grau (4º–33º) e data de obtenção**.
- Data é obrigatória para uma linha preenchida e não pode estar no futuro. Datas antigas são válidas; não se exige que a ordem das datas corresponda à ordem numérica dos graus.
- Um membro não pode ter o mesmo grau duplicado. A validação deve retornar erro legível e não salvar parcialmente o formulário.
- O catálogo existente deve ser semeado idempotentemente com `python manage.py seed_graus`, disponibilizando exatamente os graus 4–33 antes de usar o formset. Não executar semeadura em import de módulo/startup.
- Todas as gravações devem validar que o membro e o registro pertencem ao mesmo tenant autorizado e ocorrer dentro de uma transação.
- O grau mais alto continua sendo derivado do histórico para consumidores existentes; não será armazenado como estado redundante.
- Remover de `Membro` os campos `data_iniciacao`, `data_passagem` e `data_elevacao`, seus inputs/saídas locais e as referências de validação correspondentes. Não fazer backfill: o usuário confirmou que os dados atuais são de teste e não contêm informação real.
- Remover somente `Membro.data_passagem`; `HistoricoCargo.data_passagem` e campos externos do GPRB permanecem fora deste escopo.
- O histórico atualmente existente foi confirmado como dado de teste. Sua limpeza será feita por comando explícito e protegido, nunca automaticamente ao aplicar uma migração.

Exemplo conceitual de persistência:

```python
GrauMembro.objects.create(
    tenant_id=membro.tenant_id,
    membro=membro,
    grau=grau,
    data=data_obtencao,
)
```

### RF-2 — Página Acompanhamento

- Criar a página autenticada `/membros/acompanhamento/`, acessível pelo item de navegação **Acompanhamento**.
- Substituir apenas o item “Financeiro” no menu. Não remover páginas, views, URL ou dados do módulo Financeiro.
- Apresentar uma linha por membro com: nome, presença e **30 colunas de data** por padrão, uma para cada grau de 4º a 33º. Quando um ou mais corpos estiverem selecionados, mostrar somente as colunas de grau dos corpos selecionados; as colunas Membro e Presença permanecem. Vale e Loja continuam disponíveis nos filtros, mas não aparecem como colunas da tabela.
- Cada célula de grau mostra a data de obtenção em `dd/mm/aaaa`, ou `—` quando não há registro. A tabela deve permitir rolagem horizontal em telas menores.
- Incluir membros ativos e inativos por padrão; esta tela não adiciona filtro de situação nesta entrega.
- Usar o escopo de tenant já aplicado à listagem de membros: usuários comuns veem apenas o tenant autorizado; `admin_saas` segue o comportamento atual de listagem global. Usuário sem contexto/tenant permitido não recebe dados de outros tenants.
- Paginação padrão de 20 membros, preservando filtros e ordenação entre páginas.

### RF-3 — Filtros e ordenação

- Filtros GET de seleção única para Vale e Loja; remover o seletor manual de graus.
- Oferecer checkboxes estilizados de corpos: **Perfeição** (4º–14º), **Capítulo** (15º–18º), **Kadosh** (19º–30º), **Consistório** (31º–32º) e **SC33** (33º). Não há checkbox “Todos”: sem nenhum corpo marcado, listar todos os membros, mesmo sem grau registrado.
- Ao marcar/desmarcar um corpo, aplicar imediatamente os filtros via GET, preservando Vale, Loja e demais corpos selecionados. Corpos selecionados combinam por união (**OR**).
- Manter os corpos selecionados após o GET; IDs de corpo fora da allowlist não ampliam resultados. Exibir **Filtrar** e **Limpar** logo após os checkboxes; Filtrar aplica Vale/Loja e Limpar remove todos os filtros.
- Em telas médias/grandes, Vale e Loja ficam agrupados na mesma linha; os corpos e suas ações ficam logo abaixo. Em telas estreitas, os controles empilham e quebram linha.
- Selecionar vários corpos usa semântica **OR** tanto para as linhas (o membro aparece quando possui pelo menos um grau de qualquer corpo) quanto para as colunas (exibir a união dos graus dos corpos marcados). Sem corpo selecionado, mostrar todas as colunas 4º–33º.
- Cabeçalhos de Nome e Grau permitem ordenação ascendente/descendente; padrão Nome ascendente. A tabela não expõe ordenação por Vale/Loja.
- Ordenar por Grau usa o maior grau registrado. Empates são determinísticos por nome e ID; valores ausentes ficam ao final.
- Valores de ordenação e filtros devem ser validados por allowlist/tipo, sem interpolação de SQL.

### RF-4 — Presença

- Reutilizar `tarefas.PresencaServico.percentuais` como fonte do percentual, sem criar uma segunda fórmula.
- Exibir o percentual inteiro devolvido pelo serviço atual e realçar **o nome do membro em vermelho somente quando esse percentual exibido for menor que 50%**.
- Exatamente 50% não fica vermelho. Sem chamada registrada, mostrar `—` e manter o nome na cor normal.

## Requisitos não funcionais

- Todas as consultas devem respeitar tenant e permissões no servidor, independentemente dos parâmetros GET.
- Carregar graus, Vale e Lojas em lote com relacionamentos/prefetch; não executar uma consulta de grau por membro (N+1).
- Não expor CPF, e-mail ou outros dados pessoais não solicitados na nova tabela.
- O formulário de histórico deve ser atômico: erro em qualquer linha não pode salvar parcialmente as linhas válidas.
- Não adicionar dependências de runtime para implementar a funcionalidade.
- O bundle Tailwind deve ser gerado a partir dos templates durante o build Docker e incluído no `STATIC_ROOT` da imagem; a aplicação não pode depender de `theme/static/css/dist/styles.css` ignorado/não versionado no checkout do desenvolvedor.

## Limpeza explícita dos dados de teste

Criar `python manage.py limpar_historico_graus_teste`. Sem `--confirm`, o comando apenas informa quantos registros `GrauMembro` seriam apagados. A exclusão total exige `--confirm` e imprime o número removido. O comando não deve ser chamado por migração, startup ou CI. Antes de executar fora do banco de teste, exigir confirmação operacional e backup.

## Estrutura prevista

- `contatos/models.py` — remover os três campos antigos de `Membro` e garantir o catálogo 4–33.
- `contatos/forms_graus.py` — formulário/formset de histórico, validação e isolamento de membro/tenant.
- `contatos/views/gprb_membros.py` — salvar o formset em edição do membro e remover tratamento dos campos descartados.
- `contatos/views/acompanhamento.py` — consulta, filtros, ordenação, paginação e contexto da página.
- `contatos/membros_urls.py` / `contatos/views/__init__.py` — rota autenticada da página.
- `contatos/templates/contatos/acompanhamento.html` — tabela, filtros e estados vazios.
- `contatos/templates/contatos/membro_editar.html` e `membro_detalhe.html` — substituir/remover entradas locais antigas.
- `acesso/context_processors.py` — substituir o item de menu mantendo as rotas Financeiras existentes.
- `contatos/management/commands/limpar_historico_graus_teste.py` — limpeza com dry-run e confirmação.
- `contatos/migrations/` — migration para remover somente os três campos de `Membro` e adicionar constraint de 4–33, caso necessária.
- `Dockerfile`, `.dockerignore`, `docker-compose.yml` e `.github/workflows/ci.yml` — construir e incluir o bundle Tailwind no container e validar o build no CI.
- `teste/test_acompanhamento_graus.py` e testes existentes de membros — regressão, integração, segurança de tenant e consultas.
- `.github/workflows/ci.yml` — corrigir a sintaxe YAML atual antes de usar o workflow como gate.

## Estratégia de testes — TDD obrigatório

Para cada mudança de comportamento: adicionar primeiro o teste mínimo, executá-lo e confirmar falha pelo motivo esperado; implementar o mínimo; executar novamente e confirmar aprovação; então rodar os testes relacionados. Testes de integração usam PostgreSQL conforme `core.settings_vale_test` e fixtures de tenant reais. Testes unitários podem isolar cálculo/apresentação, mas autorização, formset, migração e queries serão testados em integração.

Cobertura necessária:

- várias linhas grau/data; adicionar, atualizar e excluir; transação sem salvamento parcial;
- data obrigatória, data futura, grau fora de 4–33, duplicidade e adulteração de tenant;
- migração que remove os três campos de `Membro`, sem remover `HistoricoCargo.data_passagem`;
- comando de limpeza em dry-run e com confirmação;
- tabela com os 30 graus, datas, Vales e múltiplas Lojas;
- filtro multi-grau OR, filtros de Vale/Loja e cada ordenação em ambos sentidos;
- presets de corpo em todas as faixas, combinação OR para membros e colunas, seleção vazia com todas as colunas e sem filtro de grau; rejeição de preset desconhecido;
- tenant comum, `admin_saas`, ausência de dados/contexto, presença 49%, 50% e sem chamadas;
- consulta sem crescimento N+1 quando se aumenta a quantidade de membros na página.

## CI/CD e comandos

O workflow GitHub Actions existente (`.github/workflows/ci.yml`) tinha YAML inválido perto da linha 99; a indentação foi corrigida e o workflow valida sintaxe, migrations, Ruff dos arquivos desta feature, Bandit e pip-audit. Há CI para push/PR em `main`/`master`; não foi encontrado workflow de deploy automático. A suite completa local ainda não está verde; veja `specs/006-acompanhamento-graus/ci-full-suite-report.md`. Esta entrega não autoriza deploy automático.

Comandos de verificação previstos:

```bash
python -m pytest --create-db teste/test_acompanhamento_graus.py teste/test_membro_grau_web.py -v
python manage.py check
python manage.py makemigrations --check --dry-run
python -m pytest --create-db teste/ -v --tb=short
python -m ruff check acesso/context_processors.py contatos/forms_graus.py contatos/models.py contatos/views/gprb_membros.py contatos/views/acompanhamento.py contatos/membros_urls.py contatos/views/__init__.py contatos/management/commands/limpar_historico_graus_teste.py teste/test_acompanhamento_graus.py teste/test_membro_grau_web.py teste/test_membro_local.py teste/test_vale_navigation.py
docker build --tag gprbrcrm-ci .
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml', encoding='utf-8'))"
```

O projeto declara `Django>=5.2,<5.3` e o workflow usa Python 3.13. Os testes que usam `core.settings_vale_test` precisam de `VALE_TEST_DATABASE_URL` apontando para o PostgreSQL de teste local/CI.

## Limites

- **Sempre:** TDD, tenant-scoping no servidor, validação de datas/graus, transação atômica, preservar filtros na paginação e validar migrations/CI.
- **Pedir confirmação antes:** executar a limpeza com `--confirm` em qualquer banco que não seja o banco de teste autorizado; deploy em produção; alterar a origem externa GPRB.
- **Nunca:** apagar o módulo Financeiro; apagar `HistoricoCargo.data_passagem`; inferir datas históricas; limpar histórico durante migration/startup; confiar em tenant enviado pelo cliente.

## Critérios de sucesso

1. A página Acompanhamento apresenta uma linha por membro e exatamente 30 colunas de grau (4º–33º), com cada data correta ou `—`.
2. É possível criar, alterar e remover vários graus/datas do membro; validações falham sem gravação parcial.
3. Filtros de graus múltiplos seguem OR; Nome e Grau produzem ordem determinística; a página mostra 20 membros e preserva filtros ao paginar.
4. Nome fica vermelho para 0–49%; permanece normal para 50% ou mais e sem chamadas.
5. Usuários não conseguem consultar outros tenants; `admin_saas` segue o escopo global existente.
6. Os três campos legados são removidos de `Membro`; `HistoricoCargo.data_passagem` e as rotas financeiras continuam funcionando.
7. Testes completos, Django checks, migrations check, Ruff e workflow CI passam; nenhum deploy é disparado automaticamente.
8. Uma imagem Docker construída de um checkout limpo serve o CSS da linha Vale/Loja/Graus sem depender de artefato local ignorado.

## Questões em aberto

Nenhuma para iniciar a implementação, sujeito à revisão desta spec e das tarefas pelo usuário.
