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

O repositório já vem com `Dockerfile`, `docker-compose.yml`, `entrypoint.sh`, `nginx.conf` e `.env.production.example`.

1. **Pré-requisitos**: Docker + Docker Compose na VPS e o domínio `saldoreaa.cloud` apontando para o IP do servidor.
2. **Clone e configure**:

   ```bash
   git clone git@github.com:MosandosSantos/saldejacarepagua.git
   cd saldejacarepagua
   cp .env.production.example .env
   # edite TODOS os valores marcados com TROQUE
   ```

3. **Gere os segredos** — o script faz isso e pede a senha do Postgres:

   ```bash
   ./scripts/init-secrets.sh
   ```

   Ou gere manualmente (um comando para cada):

   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(64))"  # DJANGO_SECRET_KEY
   python3 -c "import secrets; print(secrets.token_urlsafe(48))"  # JWT_SECRET
   python3 -c "import secrets; print(secrets.token_urlsafe(48))"  # CRYPTO_KEY
   ```

4. **Variáveis obrigatórias** — sem elas o app **aborta o boot** (fail-fast, por segurança):
   - `DJANGO_SECRET_KEY`, `JWT_SECRET` e `CRYPTO_KEY` — segredos gerados acima
   - `DB_PASSWORD` — senha longa, de preferência só com letras/números
   - `DJANGO_ALLOWED_HOSTS=saldoreaa.cloud,www.saldoreaa.cloud,localhost,127.0.0.1`
   - `CSRF_TRUSTED_ORIGINS=https://saldoreaa.cloud,https://www.saldoreaa.cloud`
   - `SEO_SITE_URL=https://saldoreaa.cloud`
   - `CLOUDFLARE_TURNSTILE_SITE_KEY` e `CLOUDFLARE_TURNSTILE_SECRET_KEY` — chaves reais
   - O Compose monta a `DATABASE_URL` a partir de `DB_NAME`, `DB_USER` e `DB_PASSWORD`.

5. **Subir os containers**:

   ```bash
   docker compose up -d --build
   docker compose logs -f app
   ```

   O `entrypoint.sh` aguarda Postgres/Redis, roda `migrate` e inicia o
   `uvicorn core.asgi` — **Django (painel web) e FastAPI (`/api/v1`, Swagger em `/docs`)**
   no mesmo processo/porta (`8111`).

   > Em uma VPS nova, o volume do Postgres é criado com a senha do `.env`. Se o
   > volume `postgres_data` já existir, mudar `DB_PASSWORD` no `.env` não altera
   > a senha do banco; mantenha a senha atual ou altere no Postgres antes.

6. **HTTPS**: coloque Nginx/Caddy no host na frente de `http://127.0.0.1:8111` e
   emita o certificado com Certbot/Let's Encrypt. O healthcheck usa `/healthz/`.
   Só mantenha `DJANGO_HSTS_SECONDS=31536000` depois de validar o HTTPS.
   Há um exemplo pronto em `deploy/nginx-saldoreaa.conf.example` (ajuste o caminho do `media`).
   > Se preferir o perfil `nginx` do Compose (`docker compose --profile production up -d`),
   > não suba outro Nginx no host: os dois disputam as portas 80/443.

7. **Firewall**: libere apenas `22`, `80` e `443`. Postgres e Redis já são
   publicados somente em `127.0.0.1` pelo Compose; não os exponha na internet.

8. **Carga de demonstração** (opcional): `docker compose exec app python manage.py seed_dados`.

> Sem `DJANGO_DEBUG=1` o app roda em modo produção: cookies Secure, HSTS,
> segredos obrigatórios e fail-closed. O redirect http→https fica no proxy
> (`DJANGO_SSL_REDIRECT=0`); use `1` apenas se não houver proxy.

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
