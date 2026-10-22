# Arquitetura — SAL DA BRITÂNEA CRM (legado/atual)

> Runtime do CRM após o cutover: banco Docker único `saldabritanea`, restaurado do banco Docker `gprbr`.
> Docs de produto: `DOCS/PRD.md` · Docs técnica: `DOCS/README.md` · Especificações futuras: `specs/`.

## Visão geral

Painel web em **Django 5.2** (templates DTL + Tailwind) e API JSON em **FastAPI**, rodando **no mesmo processo ASGI** na porta `8888`, sobre **PostgreSQL 15 no Docker Compose**, com **um único banco ativo: `saldabritanea`**. Esse banco contém a cópia de `gprbr`; uma instância externa de mesmo nome permanece intocada e fora do runtime.

```
Browser ──► Django (sessão cookie) ──► Views ──► ORM/Repositórios ──► Docker PostgreSQL (saldabritanea)
Browser ──► /api/v1 (JWT)  ──► FastAPI Routes ──► Services ──► Repositories ──► Docker PostgreSQL (saldabritanea)
```

| Camada | Tecnologia | Porta |
|--------|------------|-------|
| Painel web | Django 5.2 + DTL + django-tailwind (design system **HAZON**) | **8888** |
| API JSON | FastAPI (`/api/v1`, Swagger em `/docs`) | 8888 |
| Banco ativo do CRM | PostgreSQL 15 (`gprbr-db`, Docker Compose) | 5432 |
| Front estático legado | `server.js` Node | 3001 (referência) |

## Apps Django (`INSTALLED_APPS`)

| App | Responsabilidade |
|-----|------------------|
| `core` | settings, urls raiz, `dominio.py` (etapas/nichos/segmentos), `templatetags/seguranca`, pacote `core/gprb` (integração SQL direta desativada durante o cutover) |
| `acesso` | login/logout por sessão, papéis, equipe, context processor (NAV) |
| `contatos` | Vales (cadastro local via ORM), Membros, Lojas, Financeiro (placeholder) |
| `dashboard` | KPIs, funil, rankings, partials GPRB |
| `recepcao` | Fluxo de recepção |
| `tarefas` | Follow-ups (agenda consolidada) |
| `emails` / `campanhas` / `automacoes` / `discador` / `relatorios` | Motor marketing-vendas |
| `gestao` | Inscrições de congresso (GEOD-CEOD) |
| `candidatos` | Candidatos a membro |
| `funil` | Kanban drag & drop |
| `tailwind` / `theme` | Build e tokens do design system |

## Acesso a dados durante o cutover

1. **ORM Django** (`DATABASE_URL`/`PG*`) — única conexão ativa do app; aponta ao serviço Docker `db`, banco `saldabritanea`. O CRUD de Vale usa o modelo local `contatos.Vale` (`public.vales`), escopado por tenant.
2. **SQL cru via psycopg 3** para GPRB — `GPRB_DB_ENABLED=False`; o app não recebe os `GPRB_DB_*` externos. Fluxos de Loja/Membro que dependem de tabelas GPRB não copiadas podem ficar degradados; o CRUD local de Vale não os consulta.
3. A instância PostgreSQL externa também chamada `saldabritanea` não é consultada nem alterada pelo processo da aplicação.

## Multi-tenant

- Toda consulta web escopada por `tenant_id` da sessão; `admin_saas` (sem tenant) enxerga tudo.
- Decisão inegociável: dados **nunca** cruzam tenants.
- Tenant operacional atual: código `GPRB`.

## Frontend

- Templates DTL em cada app + base em `templates/base/basic.html` (header, NAV, favicon bandeira UK).
- Tailwind compilado para `theme/static/css/dist/styles.css`; tokens HAZON em `theme/static_src/tailwind.config.js`.
- Paleta escura teal/night; fontes `Manrope` (sans) e `Fraunces` (display).
- Branding Sal da Britânea: bandeira UK (`static/img/bandeira-uk.svg`) no login, header, menu mobile e favicon.

## Autenticação

- Web: sessão Django; decorators `web_login_required` / `web_requer_edicao` / escopo por papel (`viewer` só leitura).
- Durante o cutover, a autenticação usa somente `usuarios` locais (hash `make_password`); a autenticação/espelhamento GPRB fica suspensa até a etapa funcional posterior.
- API: JWT (`api/v1/services/auth_service.py`), exclusivo da API.
- Rate limit de login: 5 tentativas (cache Django).

## Infraestrutura

- **Runtime atual**: serviço PostgreSQL e app Django/FastAPI em Docker Compose; o volume PostgreSQL existente é mantido durante o cutover.
- Se executar Django nativamente no Windows, configurar `DATABASE_URL`/`PG*` para o host/porta publicados pelo Compose; não apontar para a instância PostgreSQL externa de mesmo nome.
- **Deploy (opcional)**: VPS Contabo via `Dockerfile` + `docker-compose.yml` (entrypoint roda `migrate`; ASGI único; healthcheck `/healthz/`).
- Backups `pg_dump -Fc` em `backups/`.

## Estrutura de pastas (essencial)

```
core/           settings/urls/dominio + core/gprb (conexão e SQL base)
acesso/ contatos/ dashboard/ recepcao/ tarefas/ funil/
gestao/ candidatos/ emails/ campanhas/ automacoes/ discador/ relatorios/
api/            FastAPI (v1: routes→services→repositories)
repositories/   SQL cru do modelo GPRB
templates/      base compartilhada
theme/          django-tailwind (HAZON)
teste/          suíte pytest (41 arquivos)
specs/          documentação as-is (esta pasta) + specs futuras
DOCS/           README master + PRD
_legacy/        código herdado inativo (não referenciar em código novo)
```
