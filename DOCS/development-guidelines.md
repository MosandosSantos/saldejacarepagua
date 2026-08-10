# Guidelines de desenvolvimento

Convenções adotadas no projeto. Siga-as ao contribuir.

## Stack (não mude sem necessidade)

- **Backend web**: Django 5.2 + templates DTL (sem SPA).
- **API**: FastAPI (`/api/v1`) usando o **ORM do Django** (não criar outro ORM).
- **Banco**: PostgreSQL (psycopg 3).
- **Estilo**: Tailwind (django-tailwind) + componentes `hazon-*` do design system.
- **Testes**: pytest + pytest-django (suite em `teste/`).

## Estrutura de código

- Um **app Django por módulo de negócio** (`contatos`, `discador`, ...).
- Views web são **funções** (`def`) com decorators de acesso — não class-based
  views (padrão do projeto).
- A API usa a separação **route → service → repository**: rotas finas (validação
  pydantic), services com regras, repositories com o ORM escopado por tenant.
- Lógica compartilhada de domínio (nichos, constantes) fica em `core/dominio.py`.

## Regras obrigatórias

### Multi-tenancy
- **Toda** consulta de negócio deve ser escopada: web com `filtro_tenant(request,
  qs)`; API passando `tenant_id` ao repository.
- Nunca confie em um id vindo do cliente para cruzar tenants — valide contra o
  tenant da sessão/JWT (id de outro tenant = 404/ignorado).

### Acesso web
- Toda view que renderiza tela interna: `@web_login_required` (sempre) + o nível de
  autorização adequado (`@web_requer_admin` para gestão, `@web_requer_edicao`
  quando viewer não pode editar).
- Ordem dos decorators (de cima para baixo): `web_login_required` primeiro, depois
  `web_requer_admin`/`web_requer_edicao`.

### Segurança
- Segredos sempre no `.env` (nunca no código). Use `core/segredos.py` para
  criptografar o que for persistido.
- Exportações: CSV com BOM UTF-8, separador `;` e proteção contra injeção de
  fórmula (`_csv_seguro`). Nomes de arquivo fixos (sem input do usuário).
- Não relaxar CSP/headers sem motivo documentado.

### Frontend
- Use os componentes do design system (`hazon-card`, `hazon-btn`,
  `hazon-btn-primary`/`-ghost`/`-danger`, `hazon-form`, `hazon-th`/`hazon-td`,
  `hazon-chip`, `hazon-search`). Não crie estilos manuais duplicados.
- Ações destrutivas: `hazon-btn-danger` (ou `-solid`).
- Textos sempre em **português brasileiro**, com acentos corretos.
- Gráficos: SVG gerado em Python no padrão do dashboard (`_funnel_svg`,
  `_timeline_svg`, `_linhas_svg`) — sem biblioteca JS de gráficos.

### Banco
- Campos de auditoria: `created_at` (auto_now_add) e `updated_at` (auto_now) nos
  modelos de negócio.
- Índices em campos de busca frequente (`db_index=True`), ex.: `tel_normalizado`.
- Novos modelos exigem migração (`makemigrations` + `migrate`) e o teste deve rodar
  com `--check` sem pendências.

## Testes

- Suite em `teste/`, fixtures compartilhadas em `teste/conftest.py`
  (`tenant_aurora`, `tenant_beta`, `admin_company`, `usuario_operacional`,
  `admin_saas`, `headers_*`).
- Nomeie arquivos por fase/módulo: `test_fase_<letra>_<assunto>.py`.
- Sempre cubra: **isolamento por tenant** (id de outro tenant não vaza), RBAC
  (anônimo/operacional/admin) e o fluxo feliz.
- Rate limiting é desligado nos testes pelo conftest.
- Rodar: `python -m pytest teste/` (ou um arquivo específico).
- Antes de terminar: `python manage.py check` e
  `python manage.py makemigrations --check --dry-run` (sem saída = ok).

## Comandos úteis

```bash
python manage.py runserver 8000          # painel web
uvicorn api.main:app --port 8000         # API (mesma porta)
python manage.py tailwind start          # Tailwind em watch (dev)
python manage.py tailwind build          # build do CSS
python -m pytest teste/                  # suíte completa
python manage.py seed_usuarios           # usuários de seed
python manage.py verificar_estagnados    # automações de estagnados
python manage.py enviar_relatorio        # relatório por e-mail (simulação sem SMTP)
```
