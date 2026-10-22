# GPRBRCRM

CRM multi-tenant de vendas (GPRBRCRM) com painel web em **Django (templates DTL + Tailwind)**, API REST em **FastAPI** e banco **PostgreSQL**.

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

## Deploy em VPS (Contabo)

O repositório já vem com `Dockerfile`, `docker-compose.yml`, `entrypoint.sh`, `nginx.conf` e `.env.example`.

1. **Pré-requisitos**: Docker + Docker Compose na VPS e o domínio `saldoreaa.cloud` apontando para o IP do servidor.
2. **Clone e configure**:

   ```bash
   git clone git@github.com:MosandosSantos/saldejacarepagua.git
   cd saldejacarepagua
   cp .env.example .env
   # edite o .env com os segredos e o domínio reais
   ```

3. **Variáveis de ambiente** — obrigatórias em produção, sem elas o app **aborta o boot** (fail-fast, por segurança):
   - `DJANGO_SECRET_KEY` — gere com `python -c "import secrets; print(secrets.token_urlsafe(48))"`
   - `JWT_SECRET` — outro segredo aleatório
   - `CRYPTO_KEY` (recomendado)
   - `DATABASE_URL` — `postgresql://usuario:senha@db:5432/banco`
   - `DJANGO_ALLOWED_HOSTS=saldoreaa.cloud,www.saldoreaa.cloud`
   - `CSRF_TRUSTED_ORIGINS=https://saldoreaa.cloud,https://www.saldoreaa.cloud`
   - `SEO_SITE_URL=https://saldoreaa.cloud`
4. **Subir os containers**:

   ```bash
   docker compose up -d --build
   ```

   O `entrypoint.sh` aguarda Postgres/Redis, roda `migrate` e inicia o
   `uvicorn core.asgi` — **Django (painel web) e FastAPI (`/api/v1`, Swagger em `/docs`)**
   no mesmo processo/porta (`8111`).
5. **HTTPS**: coloque Nginx/Caddy na frente do container (porta `8111`) e emita o
   certificado com Certbot/Let's Encrypt. O healthcheck usa `/healthz/`.
6. **Carga de demonstração** (opcional): `docker compose exec app python manage.py seed_dados`.

> Sem `DJANGO_DEBUG=1` o app roda em modo produção: cookies Secure, HSTS,
> segredos obrigatórios e fail-closed. O redirect http→https é opcional
> (`DJANGO_SSL_REDIRECT=1`) — com Nginx/Caddy o redirecionamento pode ser
> feito no próprio proxy.

## Usuários de seed

Após rodar `python manage.py seed_usuarios`, as credenciais são geradas
aleatoriamente e salvas em `.env-seed` (não versionado).

| E-mail | Papel |
|--------|-------|
| admin@gprbr.com | admin_saas |
| carlos@lojavirtual.com | admin_company |
| ana@lojavirtual.com | operacional |
| pedro@lojavirtual.com | viewer |

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

## API Reference

### Endpoints Principais

| Método | Endpoint | Descrição | Auth |
|--------|----------|-----------|------|
| POST | `/api/v1/auth/login` | Login e obter JWT | Não |
| GET | `/api/v1/contatos/` | Listar contatos | JWT |
| POST | `/api/v1/contatos/` | Criar contato | JWT |
| GET | `/api/v1/negocios/` | Listar negócios | JWT |
| POST | `/api/v1/negocios/` | Criar negócio | JWT |
| GET | `/api/v1/tarefas/` | Listar tarefas | JWT |

### Autenticação

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "senha": "senha123"}'

# Resposta
{"access_token": "eyJ...", "token_type": "bearer"}
```

### Exemplos de Uso

```bash
# Listar contatos
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/contatos/

# Criar contato
curl -X POST http://localhost:8000/api/v1/contatos/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"nome": "João Silva", "email": "joao@example.com"}'
```

### Documentação Interativa

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Health Check

```bash
# Verificar status do sistema
curl http://localhost:8000/healthz/

# Resposta (200 OK)
{"status": "ok", "servico": "gprbr", "database": "ok"}
```

## Testes

```powershell
# Os testes Django usam o PostgreSQL Docker e o banco de teste isolado.
docker compose run --rm --no-deps -v "$($PWD.Path):/app" --entrypoint sh app -c 'VALE_TEST_DATABASE_URL="$DATABASE_URL" python -m pytest --ds=core.settings_vale_test teste/ -v'

# Rodar com coverage no mesmo ambiente isolado
docker compose run --rm --no-deps -v "$($PWD.Path):/app" --entrypoint sh app -c 'VALE_TEST_DATABASE_URL="$DATABASE_URL" python -m pytest --ds=core.settings_vale_test teste/ --cov=. --cov-report=term-missing'

# Verificar complexidade ciclomática
python -m radon cc recepcao/ -s
```
