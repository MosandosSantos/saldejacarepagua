# Documentação do projeto

Documentação técnica do **GPRBRCRM** — CRM multi-tenant de vendas com painel web em
**Django (templates DTL + Tailwind)**, API REST em **FastAPI** e banco **PostgreSQL**.

Esta documentação descreve **somente o que existe no projeto** no momento em que foi
escrita (agosto/2026, após a Sprint 8). Nada aqui descreve funcionalidade inexistente.

## Índice

| Documento | Conteúdo |
|---|---|
| [architecture.md](architecture.md) | Visão geral da arquitetura, camadas, portas e como as partes conversam |
| [backend.md](backend.md) | Apps Django, modelos de negócio, views web e comandos de gerenciamento |
| [frontend.md](frontend.md) | Camada de templates (DTL), Tailwind, contexto da sessão e gráficos SVG |
| [database.md](database.md) | Banco PostgreSQL, tabelas por app, campos-chave e multi-tenancy |
| [security.md](security.md) | Autenticação, autorização, isolamento por empresa, headers e segredos |
| [design-system.md](design-system.md) | Tokens visuais e componentes `hazon-*` do design system |
| [api.md](api.md) | API REST `/api/v1` (FastAPI): autenticação, rotas e padrões |
| [development-guidelines.md](development-guidelines.md) | Convenções para contribuir com o código |

## Como executar

Veja o [README.md](../README.md) na raiz do repositório (setup, seed e servidores).

## Referência rápida

- **Painel web**: `python manage.py runserver 8000` → `http://localhost:8000`
- **API**: `uvicorn api.main:app --port 8000` → `http://localhost:8000/docs` (Swagger)
- **Testes**: `python -m pytest teste/` (463 testes, conforme Sprint 8)
- **Tailwind**: `python manage.py tailwind start` (dev) / `python manage.py tailwind build` (build)

## Migração do banco Docker

O CRM usa o banco lógico `saldabritanea` no serviço PostgreSQL Compose `gprbr-db`, restaurado exclusivamente do banco Docker `gprbr`. A origem e seu volume permanecem preservados para rollback. A instância PostgreSQL externa de mesmo nome não é origem, destino nem é acessada pelo app. A conexão SQL direta GPRB fica desativada; recursos que dependem dessas tabelas foram adiados.

Detalhes: [plano de migração](superpowers/plans/2026-10-11-saldabritanea-docker-migration.md) e [inventário do banco](../specs/legacy/database.md).
