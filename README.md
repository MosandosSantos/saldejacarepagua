# CronosCRM

CRM multi-tenant de vendas (CronosCRM) com painel web em **Django (templates DTL + Tailwind)**, API REST em **FastAPI** e banco **PostgreSQL**.

## Arquitetura

| Camada | Tecnologia | Porta |
|--------|------------|-------|
| Painel web (login, dashboard, funil, contatos, agenda) | Django 5.2 + templates DTL + django-tailwind | `8000` (`DJANGO_PORT`) |
| API JSON (`/api/v1`) | FastAPI | `8000` |
| HTML estático antigo (legado) | Node `server.js` | `3001` |

- Django usa apenas o ORM + camada de templates (autenticação por **sessão**, JWT é exclusivo da API).
- Multi-tenant: toda consulta web é escopada por `tenant_id` da sessão; usuário sem tenant (admin_saas) enxerga tudo.

## Setup

```powershell
# 1. Ambiente
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

# 2. Banco (PostgreSQL local, ou variáveis PG* do .env)
.\.venv\Scripts\python manage.py migrate

# 3. Tailwind (gera theme/static/css/dist/styles.css)
.\.venv\Scripts\python manage.py tailwind install   # 1ª vez (npm)
.\.venv\Scripts\python manage.py tailwind start     # watch em dev (ou tailwind build)

# 4. Servidor web
.\.venv\Scripts\python manage.py runserver 8000
```

> Requer Node.js (npm) para o Tailwind. `NPM_BIN_PATH` já está apontando para `C:\Program Files\nodejs\npm.cmd` em `core/settings.py`.

## Deploy no Railway

O repositório já vem com `Dockerfile`, `Procfile`, `railway.json` e `.env.example` — o deploy
é: conectar o repo e adicionar o Postgres.

1. **Crie o projeto** no Railway → *Deploy from GitHub repo* → escolha o repositório.
2. **Adicione o Postgres**: *Create* → *Database* → *Add PostgreSQL*. O app lê a
   `DATABASE_URL` automaticamente (em dev continuam valendo as variáveis `PG*` do `.env`).
3. **Variáveis de ambiente** (aba *Variables* do serviço web) — obrigatórias em produção,
   sem elas o app **aborta o boot** (fail-fast, por segurança):
   - `DJANGO_SECRET_KEY` — gere com `python -c "import secrets; print(secrets.token_urlsafe(48))"`
   - `JWT_SECRET` — outro segredo aleatório
   - `CRYPTO_KEY` (recomendado)
   - `DJANGO_ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` — apenas se usar **domínio próprio**
     (o `*.up.railway.app` gerado é aceito por padrão)
4. **Deploy**: o `Dockerfile` instala as dependências, compila o Tailwind e roda
   `collectstatic`; o `Procfile` executa `migrate` antes de subir (release) e inicia o
   `uvicorn core.asgi` — **Django (painel web) e FastAPI (`/api/v1`, Swagger em `/docs`)**
   no mesmo processo/porta.
5. **Domínio público**: *Settings* → *Networking* → *Generate Domain*. O healthcheck usa
   `/healthz/` (definido no `railway.json`).
6. **Carga de demonstração** (opcional): `railway run python manage.py seed_dados`.

> Sem `DJANGO_DEBUG=1` o app roda em modo produção: cookies Secure, HSTS,
> segredos obrigatórios e fail-closed. O redirect http→https é opcional
> (`DJANGO_SSL_REDIRECT=1`) — o HSTS e o edge do Railway já cobrem HTTPS.

## Usuários de seed

| E-mail | Senha | Papel |
|--------|-------|-------|
| admin@esferacrm.com | senha123 | admin_saas |
| dona@aurora.com | senha123 | dono (tenant Aurora) |
| ana@aurora.com | senha123 | recepção (tenant Aurora) |

## Apps web

- `acesso` — login/logout por sessão, decorators (`web_login_required`, `filtro_tenant`), context processor `web_sessao`.
- `dashboard` — KPIs, timeline, conversão por etapa, funil, movimentações recentes (`/dashboard/`).
- `funil` — kanban com drag & drop (`/funil/`, mover via POST).
- `contatos` — lista/busca, ficha, cadastro/edição/exclusão (`/contatos/`).
- `tarefas` — follow-ups e lembretes com vencimento e horário (`/tarefas/`; `/agenda/` redireciona para cá).
- `theme` — app do django-tailwind (paleta teal em `tailwind.config.js`).

## Notas

- Domínios compartilhados (etapas do funil, segmentos) em `core/dominio.py`.
- O antigo front estático (`index.html`, `server.js`) permanece no repositório como referência/legado.
