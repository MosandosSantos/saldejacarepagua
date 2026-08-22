# Arquitetura

## Visão geral

O CRMCronos.Cloud é um sistema **monolítico em duas camadas HTTP** sobre o mesmo banco
PostgreSQL:

| Camada | Tecnologia | Porta | O que faz |
|---|---|---|---|
| **Painel web** | Django 5.2 + templates DTL + django-tailwind | `8000` | Login por sessão, dashboard, funil, contatos, agenda, discador, relatórios |
| **API REST** | FastAPI (usa o ORM do Django) | `8000` (`/api/v1`) | Endpoints JSON para integrações, autenticados por JWT |
| **HTML estático legado** | Node `server.js` | `3001` | Front estático antigo, mantido apenas como referência |

O FastAPI é montado no mesmo processo/servidor do Django (mesma porta), mas é um
aplicativo separado (`api/main.py`), iniciado via `uvicorn`. Ambos compartilham as
configurações em `core/settings.py` e o mesmo banco.

## Componentes

```text
core/                  Configuração central
├── settings.py        Variáveis de ambiente, apps, segurança, e-mail
├── urls.py            Rotas web raiz (inclui os apps)
├── middleware.py      SecurityHeadersMiddleware (aplica CSP)
├── dominio.py         Nichos de negócio e domínios compartilhados
├── segredos.py        Criptografia AES-256-GCM de segredos
api/                   API REST FastAPI
└── v1/                router, rotas, schemas (pydantic), services, repositories
<app>/                 Cada módulo de negócio (Django app)
    models.py          Modelos (tabelas)
    views.py           Views web (funções que renderizam DTL)
    urls.py            Rotas do app
    templates/<app>/   Templates do app
    management/        Comandos de gerenciamento (quando existem)
theme/                 App do django-tailwind (styles.css, tailwind.config.js)
teste/                 Suite pytest (463 testes, fixtures em conftest.py)
```

## Apps de negócio

| App | Responsabilidade |
|---|---|
| `acesso` | Tenant, usuários, papéis (RBAC), login por sessão, convites, metas por vendedor |
| `contatos` | Contatos, negócios (pipeline), carteiras, tags, campos personalizados, notas, movimentações, importação CSV, orçamento PDF |
| `dashboard` | KPIs, funil, timeline, conversão, metas e gráficos SVG |
| `funil` | Etapas do funil e kanban com drag & drop |
| `emails` | Modelos de e-mail, envio (SMTP ou simulação), rastreio de abertura/clique |
| `tarefas` | Tarefas por contato/responsável, prioridades, vencimento e hora (absorveu a antiga Agenda) |
| `automacoes` | Automações no-code (gatilho + ações), verificação de negócios estagnados |
| `campanhas` | Campanhas de e-mail |
| `discador` | Filas de chamadas, scripts, registro de chamadas, softphone |
| `relatorios` | Relatório gerencial (KPIs de cobrança, filtros, exportação CSV/PDF) |

## Multi-tenancy

- Toda consulta web é escopada por **`tenant_id`** vindo da sessão
  (`acesso.decorators.filtro_tenant`). Usuário sem tenant (`admin_saas`) enxerga tudo.
- A API escopa pelo tenant do usuário do JWT.
- Isolamento é **aplicado na consulta** (cada view/endpoint filtra), não por banco
  separado.

## Fluxo de uma requisição web

1. Navegador → Django (`django.contrib.sessions`).
2. Middlewares de segurança aplicam headers (CSP via `core/middleware.py`).
3. Context processor `acesso.context_processors.web_sessao` injeta o usuário logado.
4. A view valida autenticação/autorização (decorators `web_login_required`,
   `web_requer_admin`, `web_requer_edicao`).
5. A view consulta o banco via ORM (sempre com `filtro_tenant`) e renderiza o template.

## Fluxo de uma requisição à API

1. Cliente → FastAPI (`/api/v1`, rate limit global 300 req/min por IP em produção).
2. Dependência `get_current_user` valida o JWT Bearer.
3. Dependência `require_roles(...)` valida o papel (RBAC).
4. Rota → service → repository (ORM do Django) → schema pydantic → JSON.
