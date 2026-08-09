# API REST (`/api/v1`)

API JSON em **FastAPI** usando o ORM do Django. Documentação interativa (Swagger)
em `http://localhost:8000/docs`.

- Prefixo: `/api/v1`
- Formato: JSON (schemas **pydantic** em `api/v1/schemas/`)
- Organização: rotas em `api/v1/routes/`, lógica em `api/v1/services/`, acesso a
  dados em `api/v1/repositories/`

## Autenticação e autorização

- `POST /api/v1/auth/login` — body `{email, senha}` → `{access_token, usuario}`.
- Bearer token JWT (validade 7 dias) em `Authorization: Bearer <token>`.
- Dependências:
  - `get_current_user` — exige token válido (401 em token ausente/expirado/inválido).
  - `require_roles('admin_saas', 'admin_company')` — restringe por papel (403).
- Rate limit global: 300 req/min por IP (em produção).

## Rotas

### auth
| Método | Rota | Descrição |
|---|---|---|
| POST | `/auth/login` | Login (JWT) |
| GET | `/auth/me` | Usuário autenticado |

### contatos
| Método | Rota | Descrição |
|---|---|---|
| GET/POST | `/contatos` | Listar/criar contatos |
| GET | `/contatos/{id}` | Detalhe |
| PUT | `/contatos/{id}` | Atualizar |
| PATCH | `/contatos/{id}/stage` | Mover de etapa do funil |
| DELETE | `/contatos/{id}` | Excluir (com validação de permissões) |

### carteiras
| Método | Rota | Descrição |
|---|---|---|
| GET/POST | `/carteiras` | Listar/criar carteiras |
| DELETE | `/carteiras/{id}` | Excluir |

### campanhas
| Método | Rota | Descrição |
|---|---|---|
| GET/POST | `/campanhas` | Listar/criar campanhas |

### discador
| Método | Rota | Descrição |
|---|---|---|
| GET/POST | `/discador/filas` | Listar/criar filas |
| GET | `/discador/filas/{id}/contatos` | Contatos da fila (ordenados) |
| POST | `/discador/filas/{id}/chamar` | Iniciar chamada (retorna URI do softphone) |
| POST | `/discador/chamadas/{id}/resultado` | Registrar resultado da chamada |
| GET | `/discador/scripts` | Listar scripts |

### acordos
| Método | Rota | Descrição |
|---|---|---|
| GET | `/acordos` | Listar acordos |
| POST | `/acordos/simular` | Simular opções de pagamento/desconto |
| POST | `/acordos` | Criar acordo (gera PIX se aplicável) |
| POST | `/acordos/{id}/resultado` | Registrar resultado (pago/recusado) |

### agendamentos
| Método | Rota | Descrição |
|---|---|---|
| GET | `/agendamentos` | Listar agendamentos |

### usuarios (admin)
| Método | Rota | Descrição |
|---|---|---|
| GET/POST | `/usuarios` | Listar/criar usuários (admin_saas) |

### tenants (admin)
| Método | Rota | Descrição |
|---|---|---|
| GET/POST | `/tenants` | Listar/criar empresas (admin_saas) |

## Padrões

- **Schemas**: pydantic (`schemas/*.py`) validam entrada/saída; rotas declaram
  `response_model`.
- **Repositories**: isolam o ORM (`repositories/*_repository.py`), recebendo o
  `tenant_id` para escopar consultas.
- **Services**: regras de negócio (ex.: `auth_service` gera/valida JWT,
  `contato_service` normaliza telefone, `agendamento_service` calcula dia útil).
- **Erros**: 401 (não autenticado), 403 (sem papel), 404 (não encontrado/não do
  tenant), 409 (conflito), 422 (validação pydantic).
- **CORS**: liberado (`allow_origins=['*']`) — API pública para integrações.

## Exemplos

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"dona@aurora.com","senha":"senha123"}'

# Listar contatos
curl http://localhost:8000/api/v1/contatos \
  -H "Authorization: Bearer $TOKEN"
```
