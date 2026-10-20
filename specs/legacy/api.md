# API REST — `/api/v1` (legado/atual)

> FastAPI no mesmo processo ASGI do Django (porta `8888`). Autenticação **JWT exclusiva da API** (web usa sessão).
> Swagger: `http://localhost:8888/docs` · ReDoc: `http://localhost:8888/redoc`

## Camadas (`api/v1/`)

```
routes/        → endpoints (FastAPI APIRouter)
services/      → regras de negócio (auth_service, contato_service, usuario_service)
repositories/  → acesso a dados (contato_repository, tenant_repository, usuario_repository)
schemas/       → schemas Pydantic
deps.py        → dependências (auth JWT, sessão DB, tenant)
rate_limit.py  → rate limiting da API
router.py      → agrega todos os routers
```

Padrão: **route → service → repository** (sem SQL em route/service).

## Routers registrados

| Arquivo | Domínio |
|---------|---------|
| `routes/auth.py` | Login JWT |
| `routes/contatos.py` | Contatos (CRUD) |
| `routes/usuarios.py` | Usuários |
| `routes/tenants.py` | Tenants |
| `routes/campanhas.py` | Campanhas |
| `routes/carteiras.py` | Carteiras |
| `routes/discador.py` | Discador (filas/scripts/chamadas) |

## Endpoints principais

| Método | Endpoint | Descrição | Auth |
|--------|----------|-----------|------|
| POST | `/api/v1/auth/login` | Login e emissão do JWT | Não |
| GET | `/api/v1/contatos/` | Listar contatos | JWT |
| POST | `/api/v1/contatos/` | Criar contato | JWT |
| GET | `/api/v1/negocios/`* | Negócios (funil) | JWT |
| GET | `/api/v1/tarefas/`* | Tarefas | JWT |

\* conforme README legado; confirmar presença real via `/docs` antes de consumir.

## Exemplos

```bash
# Login
curl -X POST http://localhost:8888/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "senha": "senha123"}'
# → {"access_token": "eyJ...", "token_type": "bearer"}

# Consumo autenticado
curl -H "Authorization: Bearer <token>" http://localhost:8888/api/v1/contatos/
```

## Health check (sem auth)

```bash
curl http://localhost:8888/healthz/
# {"status": "ok", "servico": "gprbr", "database": "ok"}
```

`healthz` (`core/urls.py`) valida app + conexão com o banco (`SELECT 1`); 503 em `degraded`.

## Notas

- RBAC da API coberto por `teste/test_rbac_api.py` (papéis admin_saas/admin_company/operacional/viewer).
- **A API não expõe o modelo GPRB** (member/loja/prefeitura) — esse domínio é exclusivo das views web + repositórios SQL. Expô-lo via API é um recurso futuro a especificar.
- Em produção (`DJANGO_DEBUG` desligado): CORS restrito por `CORS_ALLOWED_ORIGINS`, segredos obrigatórios (fail-fast no boot).
