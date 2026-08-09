# Segurança

Postura de segurança aplicada ao longo das fases D (Fase D — Segurança) e S8
(Sprint 8 — revisão de interface e segurança). Tudo abaixo **existe** no projeto.

## Autenticação

| Camada | Mecanismo |
|---|---|
| **Painel web** | Sessão Django (`django.contrib.sessions`, cookie httpOnly + SameSite=Lax). Login em `/login/` via `acesso.views.login_web`. |
| **API** | JWT Bearer (HS256 via `PyJWT`), expedido em `POST /api/v1/auth/login`, validade de **7 dias** (`TOKEN_TTL_DIAS`), chave `JWT_SECRET` do `.env`. |

## Autorização (RBAC)

Papéis em `acesso/models.py`:

| Papel | Escopo |
|---|---|
| `admin_saas` | Administra a plataforma inteira (sem tenant) |
| `admin_company` | Administra a própria empresa (equipe, config, campos, exclusões) |
| `operacional` | Opera o dia a dia (cria/edita contatos, chamadas, acordos) |
| `viewer` | Somente leitura |

- Web: decorators `web_login_required`, `web_requer_admin`, `web_requer_edicao`.
  Ex.: só admin acessa `/equipe/`, `/contatos/campos/` e exclusões; viewer é
  redirecionado de ações de edição.
- API: dependency `require_roles(...)` (ex.: `require_roles('admin_saas',
  'admin_company')`) nas rotas administrativas; demais exigem login válido.

## Isolamento multi-tenant

- Toda view web consulta com `filtro_tenant(request, qs)`; ids de outros tenants
  resultam em 404 (ex.: filtro de operador de outro tenant é ignorado).
- Tabelas dependentes sem `tenant` próprio escopam pela FK: a agenda filtra por
  `contato__tenant_id` (`agendamentos/views.py`).
- A API escopa repositórios pelo `tenant_id` do usuário do JWT.
- Testes dedicados garantem o isolamento (ver `teste/test_equipe.py`,
  `teste/test_rbac_api.py`, `teste/test_fase_s_relatorios.py`).

## Headers de segurança (Fase D)

Aplicados em **todas** as respostas web:

- `Content-Security-Policy` — via `core/middleware.SecurityHeadersMiddleware`
  (`CSP_DIRETIVAS` em settings: `default-src 'self'`, script/style com
  `'unsafe-inline'` por causa dos scripts inline das telas, `frame-ancestors 'none'`,
  `object-src 'none'`, etc.). A API tem CSP própria mais restritiva
  (`default-src 'none'`, liberando apenas o CDN do Swagger UI).
- `X-Frame-Options: DENY` (`X_FRAME_OPTIONS = 'DENY'`).
- `SECURE_CONTENT_TYPE_NOSNIFF = True`.
- `SECURE_REFERRER_POLICY = 'same-origin'`.
- `SESSION_COOKIE_HTTPONLY = True`, `SESSION_COOKIE_SAMESITE = 'Lax'`,
  `CSRF_COOKIE_HTTPONLY = True`, `CSRF_COOKIE_SAMESITE = 'Lax'`.
- Em produção (`DEBUG=0`): HSTS (`SECURE_HSTS_SECONDS`), opção de redirect SSL.

## Hosts permitidos (S8)

- `ALLOWED_HOSTS` é configurável por `DJANGO_ALLOWED_HOSTS` no `.env` (anti
  host-header spoofing).
- Sem a variável: no dev (`DEBUG=1`) tudo liberado (`*`); em produção (`DEBUG=0`)
  **falha fechado** — aceita apenas `localhost`/`127.0.0.1`.

## Variáveis sensíveis

- `.env` está no `.gitignore` — `SECRET_KEY`, `JWT_SECRET`, credenciais de banco e
  de SMTP nunca entram no repositório.
- Segredos armazenados são criptografados com **AES-256-GCM**
  (`core/segredos.py`), chave derivada de `CRYPTO_KEY` (ou `SECRET_KEY`) via SHA-256.

## Proteções específicas

- **Rate limiting da API** — `api/v1/rate_limit.py`: 300 req/min por IP
  (`DJANGO_RATE_LIMIT`; com `DJANGO_TRUST_PROXY=1` usa `X-Forwarded-For`).
  Desativado nos testes pelo `teste/conftest.py`.
- **CSRF** — `CsrfViewMiddleware` ativo nas rotas web (forms enviam token).
- **Exportação segura** — CSV com BOM UTF-8 e proteção contra injeção de fórmula
  (`relatorios/views.py _csv_seguro`).
- **Sessões** — a listagem de sessões ativas (`/config/`) filtra sessões expiradas
  antes de processar (S8).
- **E-mail** — sem SMTP configurado, o envio roda em **modo simulação** (nada sai
  de verdade; registros são rastreados).

## Rotas públicas intencionais

- `/login/`, `/onboarding/`, `/convidar/<token>/` (via convite), `/captura/<token>/`
  (formulário público de captura), `/emails/aberto/<token>/` e
  `/emails/clique/<token>/<codigo>/` (pixel e links de rastreio).
- Todas as demais rotas exigem sessão válida.
