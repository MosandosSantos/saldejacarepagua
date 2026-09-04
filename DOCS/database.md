# Banco de dados (PostgreSQL)

## Configuração

- Engine: **PostgreSQL** via `psycopg` (versão 3), configurado em `core/settings.py`.
- Variáveis de ambiente (`.env`): `PGDATABASE` (padrão `gprbr`), `PGUSER`
  (padrão `postgres`), `PGPASSWORD`, `PGHOST` (padrão `localhost`), `PGPORT` (5432).
- Migrações: Django ORM (`python manage.py makemigrations` / `migrate`).
- `USE_TZ = True`, `TIME_ZONE = 'America/Sao_Paulo'` — datas armazenadas em UTC
  (timezone-aware) e exibidas em horário de Brasília.

## Modelo de dados por app

> Convenção: registros de negócio **raiz** possuem `tenant` (FK) para isolamento
> multi-empresa; tabelas **dependentes** (`Nota`, `Movimentacao`,
> `ValorCampoPersonalizado`) não têm `tenant` próprio — herdam o
> escopo da FK para `contato`/`negocio`. Quase todos os modelos têm
> `created_at`/`updated_at` (auto).

### acesso

| Tabela | Campos principais |
|---|---|
| `acesso_tenant` | nome, slug (único), nicho, meta_mensal, dono (FK usuario), token_captura, captura_ativa, softphone_schema, softphone_dominio, pix_chave, pix_recebedor, pix_cidade, created_at, updated_at |
| `acesso_usuario` | nome, email (único), senha (hash), role, tenant (FK, nullable), created_at, updated_at |
| `acesso_metavendedor` | usuario (FK), mes, valor, created_at, updated_at |
| `acesso_convite` | token (único), tenant (FK), email, papel, criado_por (FK), expira_em, usado_em, usado_por (FK), cancelado_em |

### contatos

| Tabela | Campos principais |
|---|---|
| `contatos_carteira` | nome, descricao, tenant |
| `contatos_tag` | nome, cor, tenant |
| `contatos_contato` | nome, empresa, tel, **tel_normalizado** (indexado), email, seg, procedimento, ultima_consulta, origem, pagamento, nascimento, cpf, cidade, bairro, observacoes, cnpj, razao_social, cnae, endereco, responsavel, cargo, lead_score, carteira (FK), tags (M2M), tenant |
| `contatos_negocio` | contato (FK), titulo, **stage**, valor (Decimal 12,2), principal, responsavel (FK), tenant |
| `contatos_campopersonalizado` | nome, tipo, opcoes, obrigatorio, ordem, ativo, tenant |
| `contatos_valorcampopersonalizado` | campo (FK), contato (FK), valor |
| `contatos_nota` | contato (FK), texto, autor |
| `contatos_movimentacao` | contato (FK), tipo, descricao, responsavel |

### funil

| Tabela | Campos principais |
|---|---|
| `funil_etapafunil` | tenant, **key** (única por tenant, salva em `Negocio.stage`), nome, cor, ordem, peso (probabilidade), sistema |

### emails

| Tabela | Campos principais |
|---|---|
| `emails_modeloemail` | tenant, nome, assunto, corpo |
| `emails_emailenviado` | tenant, contato (FK), modelo (FK), campanha (FK), assunto, corpo, destinatario, status, token (UUID único), enviado_em, aberto_em, cliques, ultimo_clique_em, convertido_em |

### tarefas

| Tabela | Campos principais |
|---|---|
| `tarefas_tarefa` | tenant, titulo, descricao, contato (FK), responsavel (FK), prioridade, vencimento, concluida, concluida_em, criado_por (FK) |

### automacoes

| Tabela | Campos principais |
|---|---|
| `automacoes_automacao` | tenant, nome, trigger, parametros (JSON), ativa, criado_por (FK), ultima_execucao, total_execucoes |
| `automacoes_passoautomacao` | automacao (FK), ordem, acao, parametros (JSON) |
| `automacoes_registroexecucao` | automacao (FK), contato (FK), negocio (FK), status (ok/erro), mensagem |

### campanhas

| Tabela | Campos principais |
|---|---|
| `campanhas_campanha` | nome, descricao, canal, ativa, tenant |

### discador

| Tabela | Campos principais |
|---|---|
| `discador_script` | nome, descricao, conteudo, ativa, tenant |
| `discador_fila` | nome, descricao, carteira (FK), script (FK), ordem, ativa, tenant |
| `discador_chamada` | fila (FK), contato (FK), operador (FK), status, observacao, retorno_em, tenant |

## Multi-tenancy no banco

- **Escopo por coluna**: a coluna `tenant_id` existe nas tabelas de negócio.
- Nenhuma query cruza tenants: `filtro_tenant(request, qs)` adiciona
  `qs.filter(tenant_id=tid)` em todas as views web; a API faz o mesmo via o tenant
  do usuário autenticado.
- `admin_saas` (usuário sem tenant) vê todas as empresas — usado apenas para
  administração da plataforma.
- Unicidade **por tenant** (constraints `UniqueConstraint` no banco):
  `EtapaFunil (tenant, key)`, `CampoPersonalizado (nome, tenant)`,
  `Carteira (nome, tenant)`, `Tag (nome, tenant)` e
  `ValorCampoPersonalizado (contato, campo)` — nunca globais.

## Índices relevantes

- `Contato.tel_normalizado` — `db_index=True` (busca rápida por telefone normalizado).
- `EmailEnviado.token` — UUID único (pixel de abertura / links rastreados).
- `Convite.token` — único (link de convite).
- FKs de filtro (tenant, contato, operador) contam com os índices padrão do Django.
