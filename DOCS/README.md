# SAL DA BRITÂNEA CRM

CRM multi-tenant de gestão de membros, lojas e potências, com painel web em **Django (templates DTL + Tailwind)**, API REST em **FastAPI** e banco Docker ativo **PostgreSQL: `saldabritanea`**.

Fork do GPRB CRM, rebrandado **Sal da Britânea** (identidade com bandeira do Reino Unido).

> **Documento master.** O PRD completo está em [`DOCS/PRD.md`](PRD.md).

## Arquitetura

| Camada | Tecnologia | Porta |
|--------|------------|-------|
| Painel web (login, dashboard, membros, potências, lojas, funil, agenda) | Django 5.2 + templates DTL + django-tailwind | **`8888`** |
| API JSON (`/api/v1`) | FastAPI (mesmo processo ASGI) | `8888` |
| Banco de dados do CRM | PostgreSQL 15 (Docker Compose, serviço `gprbr-db`) | `5432` |
| Front estático legado | Node `server.js` | `3001` (referência) |

- Django usa o ORM + camada de templates (autenticação por **sessão**); JWT é exclusivo da API.
- Multi-tenant: toda consulta web é escopada por `tenant_id` da sessão; usuário sem tenant (`admin_saas`) enxerga tudo.
- Durante o cutover, o acesso SQL direto ao modelo GPRB fica desativado. O app usa somente o banco Django no serviço Docker `gprbr-db`; recursos que dependem de tabelas GPRB podem ficar indisponíveis até a correção posterior.

## Banco de dados — Docker `saldabritanea` (único ativo)

O serviço PostgreSQL Docker `gprbr-db` terá um banco lógico `saldabritanea`, restaurado somente do banco Docker de origem `gprbr`. O banco `gprbr` e seu volume ficam preservados para rollback.

O banco externo antigo também se chama `saldabritanea`; ele permanece intacto e não é consultado pelo app nem usado como origem. O destino contém as 37 tabelas públicas observadas em `gprbr`; o inventário está em [`specs/legacy/database.md`](../specs/legacy/database.md).

As 13 tabelas do modelo GPRB (`tenant`, `user`, `member`, `member_loja`, `loja`, `prefeitura`, `potencia`, `rito`, `payment`, `payment_period`, `payment_status`, `meeting`, `attendance`) não são importadas nesta migração. Funcionalidades que dependem delas podem ficar indisponíveis até o trabalho posterior.

O cadastro de Vales é uma exceção local: `contatos.0015_vale` cria `public.vales` vazio no banco Docker ativo, com isolamento por tenant e contatos de Secretaria/Tesouraria; não importa a tabela GPRB `prefeitura` nem seus dados.

### Modelagem GPRB histórica (fora do destino)

- **`member_loja`** modela a relação N:N membro ↔ lojas; a primeira loja é a principal.
- **`prefeitura`** representa Potência; **`potencia`** representa a potência maçônica de origem; `rito` contém os ritos.
- A instância externa possui módulos excluídos por decisão de produto, como `class`, `inventory_item`, `dues_charge` e `_prisma_migrations`; esse schema não é copiado para o Docker.

## Setup (aplicação e banco)

> O PostgreSQL do CRM roda no Docker Compose. A porta `5432` é publicada no host; use o banco Docker `saldabritanea`, não a instância externa de mesmo nome.

```bash
# 1. Ambiente
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt

# 2. Banco — subir o Compose após criar/restaurar o banco Docker `saldabritanea`
docker compose up -d db app
docker compose exec app python manage.py migrate

# 3. Tailwind (gera theme/static/css/dist/styles.css; requer npm)
.venv/Scripts/python manage.py tailwind install   # 1ª vez
.venv/Scripts/python manage.py tailwind build

# 4. Servidor web na 8888 (sem auto-reload)
nohup .venv/Scripts/python.exe manage.py runserver 0.0.0.0:8888 --noreload > logs/runserver-8888.log 2>&1 &
```

Após editar código, **reinicie o servidor manualmente** (sem `--noreload` o processo não recarrega):

```bash
PID=$(netstat -ano | grep ":8888" | grep LISTENING | head -1 | awk '{print $NF}'); taskkill //F //PID $PID
```

## Variáveis de ambiente (.env)

| Chave | Valor no ambiente atual |
|-------|------------------------|
| `DATABASE_URL` / `PG*` | apontam para o banco Docker `saldabritanea` (ORM Django) |
| Setting Django `GPRB_DB_ENABLED` | `False` durante esta migração; SQL direto GPRB desativado |
| `GPRB_DB_*` | não são passadas ao container do app; a instância externa não é consultada |
| `DJANGO_SECRET_KEY` | segredo (obrigatório em produção) |
| `DJANGO_DEBUG` | `False` em produção (fail-closed) |

Modelo de variáveis em [`.env.example`](../.env.example). A URL interna do Compose usa o host `db`.

## Autenticação

1. Login por identificador (ex.: telefone) + senha em `/login/`.
2. O login usa as contas locais em `usuarios` (Django, hash `make_password`). A autenticação GPRB externa está indisponível durante o cutover.
3. O espelhamento automático de usuários GPRB fica suspenso até a etapa funcional posterior.
4. **Rate limit**: 5 tentativas por identificador (cache Django).
5. Papéis: `admin_saas` (sem tenant, enxerga tudo), `admin_company`, `operacional`, `viewer` (somente leitura).

## Módulos web

| Rota | App | Descrição |
|------|-----|-----------|
| `/login/`, `/logout/` | `acesso` | Sessão, rate limit, espelho local |
| `/dashboard/` | `dashboard` | KPIs, funil, rankings de lojas, ranking MX, BAII por situação |
| `/contatos/` | `contatos` | **Membros**: lista com N lojas, ficha, edição (múltiplas lojas), situação ATIVO/INATIVO |
| `/contatos/prefeituras/` | `contatos` | **Potências** (tabela `prefeitura`): CRUD sem região |
| `/contatos/lojas/` | `contatos` | **Lojas**: CRUD, vínculo à Potência, Presidente, drill-down de membros |
| `/contatos/financeiro/` | `contatos` | Financeiro (placeholder) |
| `/funil/` | `funil` | Kanban de negócios com drag & drop |
| `/tarefas/` | `tarefas` | Follow-ups com vencimento (`/agenda/` redireciona para cá) |
| `/iniciacao/` | `recepcao` | Fluxo de iniciação (alias legado: `/recepcao/`) |
| `/gestao/` | `gestao` | Inscrições de congresso (GEOD-CEOD) |
| `/candidato/` | `candidatos` | Candidatos a membro |
| `/equipe/`, `/config/` | `acesso` | Equipe do tenant e configurações |
| `/automacoes/`, `/campanhas/`, `/emails/`, `/discador/`, `/relatorios/` | respectivos | Marketing/vendas |

## Nomenclatura de negócio

| Tela/termo | Tabela/coluna real | Termo antigo |
|------------|--------------------|--------------|
| **Potência** | `prefeitura` | Prefeitura |
| **Grão-Mestre** | `prefeitura.prefeito` | Prefeito |
| **Presidente** (da loja) | `loja."deputadoMestreId"` | Deputado Mestre |
| **Situação** do membro | `member.situacao` (ATIVO/INATIVO) | Classe (MX/EN/CBCS — removida) |

## API REST

```bash
# Swagger / ReDoc
#   http://localhost:8888/docs  ·  http://localhost:8888/redoc

# Login (JWT)
curl -X POST http://localhost:8888/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "senha": "senha123"}'

# Exemplo autenticado
curl -H "Authorization: Bearer <token>" http://localhost:8888/api/v1/contatos/
```

## Health check

```bash
curl http://localhost:8888/healthz/
# {"status": "ok", "servico": "gprbr", "database": "ok"}
```

## Testes

```bash
python -m pytest teste/ -v
python -m pytest teste/ --cov=. --cov-report=term-missing
python -m radon cc recepcao/ -s
```

## Backups

O dump desta migração fica fora do repositório, em `C:\Users\mosan\AppData\Local\Temp\opencode`, para não versionar dados:

```powershell
docker exec gprbr-db pg_dump -U gprbr -Fc -d gprbr -f /tmp/gprbr-to-saldabritanea.dump
docker cp gprbr-db:/tmp/gprbr-to-saldabritanea.dump "C:\Users\mosan\AppData\Local\Temp\opencode\gprbr-to-saldabritanea-YYYYMMDD_HHMMSS.dump"
```

Histórico da migração de banco: `backups/saldogprb_backup_20261002.dump` (e equivalente do `esferasda_crm`) — feitos **antes** da criação do `saldabritanea`.

## Migração de bancos (status)

| Banco | Situação |
|-------|----------|
| Docker `saldabritanea` | Destino ativo após restore do Docker `gprbr` |
| Docker `gprbr` | Origem preservada para rollback até validação explícita |
| PostgreSQL externo `saldabritanea` | Instância de mesmo nome, intacta e não consultada |
| `saldogprb` / `esferasda_crm` | Fontes antigas desligadas; fora desta migração |
| `esferasda` | **Outro sistema (obras) — não tocar** |

> Não remover bancos nem volumes nesta entrega. Corrigir telas GPRB degradadas é trabalho posterior ao cutover.

## Design system e branding

- **HAZON**: tokens em `theme/static_src/tailwind.config.js` (paleta escura teal/night: `night`, `abyss`, `deep`, `surface`, `primary`, `accent`).
- Tipografia: `Manrope` (sans) e `Fraunces` (display).
- Branding Sal da Britânea: bandeira UK (`static/img/bandeira-uk.svg`) no login, header, menu mobile e favicon; logo "SAL DA / BRITÂNEA".

## Secao Calendario — o "Livro de Sessoes"

A segunda aba de `/agendas/` nao e um painel como os outros: e a **pagina do livro de sessoes** da Vale, aberta numa folha escura. A paleta vem do emblema Sal do Reaa (carmesi + ouro), nao do azul do resto do sistema.

| Token | Hex | Uso |
|-------|-----|-----|
| `--livro-fundo` | `#12070c` | campo do livro (mais escuro que o hero azul) |
| `--livro-celula` | `#1a0a12` | celula do dia |
| `--livro-vazia` | `#100609` | dias fora do mes (pagina ainda nao pautada) |
| `--livro-ouro` | `#d4af37` | titulo da secao, filetes, selo do dia, hora |
| `--livro-tinta` | `#f0e3c6` | titulo da sessao (tinta de pergaminho) |
| `--livro-carmim` | `#c8102e` | dia de hoje |

Regras da secao:

- **Titulo**: "Calendario da Vale de {{ VALE_NOME }}" — `VALE_NOME` vem de `settings.py` (env `VALE_NOME`, padrao `Jacarepagua`).
- **O botao "Novo Evento" nao aparece no Calendario** (a sessao e aberta pelo secretario a partir do proprio dia). Ele volta em Kanban e Lista.
- **A navegacao de mes muda de casa**: no Calendario ela faz parte do cabecalho do livro; em Lista volta para a barra de modos; em Kanban fica oculta.
- **Selo de ouro**: dia com sessao ganha um anel em ouro em volta do numero; o dia de hoje ganha o carmesim. O tipo da sessao (grau, iniciacao, ritual) continua marcado pela regua colorida a esquerda do lancamento.
- As classes vivem em `theme/static_src/src/styles.css` (prefixo `livro-`), junto dos demais tokens.

## Acessibilidade e UI (Web Interface Guidelines)

O painel segue as [Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines). As convenções adotadas:

| Tema | Convenção |
|------|-----------|
| Foco | Todo controle interativo tem anel de foco visível (`focus-visible:ring-2 focus-visible:ring-[#5b8def]/60`). Nunca `outline-none` sem substituto. |
| Movimento | `prefers-reduced-motion: reduce` desliga transições/animations (bloco global em `theme/static_src/src/styles.css`). |
| Ícones | SVG inline decorativo leva `aria-hidden="true"`. Botão/link só-ícone precisa de `aria-label`. |
| Formulário | Campo sempre com `<label for>`/`aria-label`; `autocomplete` conforme o dado; erros com `role="alert"` e junto do campo. |
| Datas e moeda | Filtros locale-aware (abaixo) — **nunca** `\|date:"d/m/Y"` hardcoded. |
| Estados | Botão submit ganha spinner + `aria-busy` automaticamente (listener global no `templates/base/basic.html`). Formulários com edição levam `data-unsaved-guard` (aviso ao sair). |
| Modais | `role="dialog"` + `aria-modal` + `tabindex="-1"`, abertos via `window.hazonModal.abrir(el)` / `.fechar(el)` (focus trap, Escape e retorno de foco). |
| Tema | `color-scheme: dark` no `:root`; `<meta name="theme-color">` sincronizado com o tema escolhido pelo usuário. |
| Destrutivo | Confirmação via atributo `data-confirm="…"` (nunca `onclick="return confirm(...)"`). |

### Filtros de formatação (`core/templatetags/formatacao.py`)

Registrados como **builtin** em `settings.TEMPLATES` — disponíveis em qualquer template, sem `{% load %}`:

| Filtro | Exemplo | Substitui |
|--------|---------|-----------|
| `\|databr` | `19/07/2026` | `\|date:"d/m/Y"` |
| `\|datahorabr` | `19/07/2026 14:30` | `\|date:"d/m/Y H:i"` |
| `\|horabr` | `14:30` | `\|date:"H:i"` |
| `\|mesanome` | `julho de 2026` | `\|date:"m/Y"` |
| `\|moedabr` | `R$ 1.234,56` | `"R$ " + valor` |
| `\|numerobr` | `1.234.567` | `\|floatformat` cru |

> Formatos **ISO** (`Y-m-d`) continuam em uso proposital onde o valor vai para `<input type="date">`, query strings ou comparação em JS.

### Varredura automática

```bash
python scripts/a11y_sweep.py            # aplica as correções mecânicas
python scripts/a11y_sweep.py --check    # apenas relatório, não grava
```

O script é **idempotente** e cobre: `aria-hidden` em SVG, `scope="col"` em `<th>`, anel de foco, reticências tipográficas, datas/moeda, dimensões de `<img>`, `aria-label` em controles só-ícone e `data-unsaved-guard` em formulários POST. Ele **não** toca em `acesso/templates/acesso/login.html`.

## Regras de Python (Python Expert Best Practices)

O código segue as regras de `Python Expert Best Practices` (prioridade 1-4: tratamento de erro, bugs comuns, clareza, estilo). Os verificadores vivem em `scripts/`:

```bash
python scripts/py_rules_scan.py            # relatorio por regra/prioridade
python scripts/check_imports.py            # importa TODOS os modulos (acha alias quebrado)
python scripts/ruff_check.py              # F821 (nome indefinido) + F811 + F401
python scripts/hoist_imports.py            # sobe imports locais redundantes ao topo
python scripts/hoist_imports.py --check    # so relatorio
python scripts/narrow_excepts.py --check   # estreita `except Exception` (preview)
python scripts/check_import_regression.py <ref-git>   # nomes perdidos vs. uma referencia
python scripts/smoke_routes.py             # roda DENTRO do container: status de cada rota
```

Regras com-zero no app (verificado por `py_rules_scan.py`):

| Regra | Prioridade | Estado |
|-------|-----------|--------|
| `no-generic-except` | HIGH | 0 |
| `no-mutable-defaults` | CRITICAL | 0 |
| `listcomp-no-side-effects` | HIGH | 0 |
| `operators-return-notimplemented` | CRITICAL | 0 |
| `unnecessary-else-blocks` | LOW | 0 |
| `no-inline-imports` redundante | MEDIUM | 0 |

Duas ressalvas do report:

- **`except Exception` que RELANÇA** não é violação — o erro não é escondido. Use-o no adaptador de lib de terceiro (ex.: `gestao/whatsapp.py` traduz a falha do pywhatkit em `ErroEnvioWhatsApp`).
- **`.get()` em dado de fronteira** (`request.POST/GET/FILES/session`) é o certo: a chave é genuinamente opcional. A regra `dict-required-keys` vale para contrato interno — aí use `d[chave]` ou valide na entrada.

`scripts/smoke_routes.py` roda dentro do container (o código e os dados vivem lá):

```bash
docker cp scripts/smoke_routes.py gprbr-app:/tmp/smoke_routes.py
docker exec gprbr-app python /tmp/smoke_routes.py
```


## Deploy (VPS Contabo — Docker)

O repositório mantém `Dockerfile`, `docker-compose.yml`, `nginx.conf` e `.env.production.example` para deploy em VPS Contabo (Django + FastAPI no mesmo processo; `entrypoint.sh` roda `migrate`; healthcheck `/healthz/`). Em produção, sem `DJANGO_DEBUG=1`: cookies Secure, HSTS, segredos obrigatórios (incluindo `JWT_SECRET` e `CRYPTO_KEY`) e fail-closed. Postgres e Redis ficam publicados apenas em `127.0.0.1`.

## Estrutura do projeto

```
core/            settings, urls, views base, domínio (etapas/nichos), gprb/connection+users+members+ranking
acesso/          login/logout, papéis, equipe, context processor (NAV)
dashboard/       KPIs e partials; repositório GPRB próprio
contatos/        membros, potências, lojas, financeiro; repositories/gprb_repository.py (camada SQL GPRB)
funil/ tarefas/ recepcao/ gestao/ candidatos/
automacoes/ campanhas/ emails/ discador/ relatorios/
api/             FastAPI (/api/v1)
repositories/    repositórios de dados (SQL cru)
templates/       base (header, NAV, favicon)
theme/           django-tailwind (tokens HAZON)
teste/           suíte pytest
DOCS/            esta documentação (README master + PRD)
backups/ logs/   artefatos de operação
```

## Documentação relacionada

- [`DOCS/PRD.md`](PRD.md) — PRD master (visão, requisitos, modelo de dados, regras de negócio)
- `.env.example` — variáveis de ambiente
