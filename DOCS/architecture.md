# Arquitetura

## Visão geral

O GPRBRCRM é um sistema **monolítico em duas camadas HTTP** sobre o mesmo banco
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
| `gestao` | Dashboard global de inscrições do evento GEOD-CEOD (**sem escopo de tenant** — área à parte) |

## Navegação (menu)

O menu é montado em `acesso/context_processors.py::_ROTAS`. Cobertura atual:

| Item do menu | Aplicações cobertas |
|---|---|
| Dashboard, Funil | `dashboard`, `funil` |
| Membros, Prefeitura, Lojas | `contatos` (camada GPRB) |
| Ranking | `tarefas:ranking` (badge de atrasadas) |
| Comunicações (link para `premium_campanhas`) | upsell premium — `campanhas`/`emails` entram por lá |
| Equipe (gestores: oficialato + `admin_company`) | cadastro de usuários **sem senha** + reenvio de link (`equipe`) |
| Usuários | página de usuários (`config`: perfil, senha; para gestores: cadastro sem senha, convites (só `admin_company`) — aparência/sessões removidas da página em 2026-09; tema continua no botão do header) |

Decisão de produto (2026-09): o menu é enxuto — **não** inclui submenus de Tarefas ou
"Operação" (Discador/Relatórios/Automações ficam acessíveis por URL; reavaliar quando
forem ativados comercialmente).

- **`gestao`** (GEOD-CEOD) é uma área interna sem item de menu de propósito: o dashboard
  agrega dados globais (sem tenant). Acesso direto por `gestao:dashboard`; não expor no
  menu padrão sem definir um papel/portão próprio (ex.: somente `admin_saas`).
- Se um app estiver em `INSTALLED_APPS`/`core/urls.py` e **não** aparecer acima, é
  área interna ou rota de serviço — atualizar esta tabela ao mudar o menu.

## `contatos`: duas camadas coexistindo

| Camada | Modelo de dados | Chaves | Views | Destino |
|---|---|---|---|---|
| **GPRB** (diretório maçônico) | SQL cru em `core/gprb.py` → banco `saldogprb` | UUID | membros, lojas, prefeituras | **Menu**: Membros/Prefeitura/Lojas |
| **CRM** (HAZON, venda) | ORM `Contato`/`Negocio`/`Carteira`/`CampoPersonalizado` | `int` | `lista`(antiga), `novo`, `detalhe`, negócios, notas, tags, carteiras, campos, leads, importar/exportar | alimenta `funil`, `dashboard`, `emails`, `discador`, `tarefas`, `automacoes`, `relatorios` |

A lista de membros (`contatos:lista`) assumiu o item "Membros" do menu; a antiga lista de
contatos CRM ficou **sem entrada na UI**. Rotas CRM que hoje não têm link de entrada
(levantamento 2026-09 — confirmar uso antes de remover):

| Rota | Referências externas à própria tela | Veredito |
|---|---|---|
| `contatos:novo`, `detalhe`, `editar`, `excluir`, negócios, notas, tags | somente fluxo interno entre essas telas | sem entrada no menu — decidir reexpor (submenu CRM premium) ou ocultar |
| `contatos:carteiras` / `carteira_detalhe` | auto-refs + upsell `premium_carteiras` | área premium — reexpor para quem contratou |
| `contatos:campos` | usado por `formulario` | segue o fluxo acima |
| `contatos:leads_pobres` | nenhuma | candidata a remoção (verificar tráfego) |
| `contatos:importar` / `modelo` | só link próprio | sem entrada — reexpor junto com a tela CRM correspondente |
| `contatos:exportar` | nenhuma | candidata a remoção (substituída por exportações do funil/relatórios) |
| `contatos:exportar_negocios` | link no `funil/kanban.html` | em uso — manter |

## Acesso: criação de usuário sem senha (ativação por link 72h)

Desde 2026-09, usuários do sistema são criados **sem senha** (PRD-USUARIOS-SEM-SENHA):

- **Criação** (`acesso/views.py::equipe` e ação `criar_usuario` do `config`): nome,
  e-mail, celular e perfil. Quem pode criar/reenviar: `ROLES_GESTORES_USUARIOS`
  (oficialato Grão Prior/Grande Chanceler/Grande Tesoureiro/Prefeito/Deputado/TI +
  `admin_company` legado). A conta nasce `pendente_senha` no tenant do gestor, com
  senha inutilizável (`!`), `criado_por` e token de ativação de 256 bits.
- **E-mail**: rotina única `acesso/ativacao.py::enviar_email_ativacao` →
  `emails.servico.enviar_mensagem` (em dev, sem SMTP, roda em modo simulação e o
  link vai ao log). Validade: 72h (`PRAZO_ATIVACAO`); reenvio limitado a 3
  (`LIMITE_REENVIOS`), gerando token novo.
- **Ativação** (`ativar_conta`, rota pública `usuario/ativar/<token>/`): token
  inválido/expirado/já usado mostram o motivo; válido → usuário define e confirma a
  senha (política `AUTH_PASSWORD_VALIDATORS`), a conta vira `ativo`, o token é
  limpo (uso único) e o login é automático.
- **Login** de usuário pendente é bloqueado em todos os caminhos (CRM local,
  fallback GPRB e Saldorer).

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
