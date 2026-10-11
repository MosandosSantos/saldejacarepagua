# Sal da Britânea CRM Constitution

## Princípios Fundamentais

### I. Banco único (NON-NEGOTIABLE)
O sistema opera com **um único banco PostgreSQL ativo: `saldabritanea` no serviço Docker `gprbr-db`**, restaurado somente a partir do banco Docker `gprbr`. O ORM Django aponta para esse banco. A conexão SQL direta GPRB (`GPRB_DB_*`) fica desativada até a migração funcional posterior; a antiga instância externa também chamada `saldabritanea` permanece intacta e não pode ser consultada pelo app. Nenhum código novo pode criar espelho/sincronização externa ou reintroduzir Prisma. O banco `esferasda` pertence a outro sistema e **nunca** pode ser tocado.

### II. Isolamento multi-tenant
Toda consulta é escopada por `tenant_id` da sessão; dados **nunca** vazam entre tenants. Decisões de produto que sacrificam esse isolamento são descartadas, sem exceção. `admin_saas` (sem tenant) enxerga tudo — é a única exceção.

### III. Repositórios como única porta de acesso a dados
Views e serviços **não montam SQL**. Todo acesso ao modelo GPRB passa por `repositories/gprb_repository.py` ou `dashboard/repositories/gprb_repository.py`. Nomes de colunas/frases SQL vivem nos repositórios; templates recebem dicts com chaves estáveis e documentadas.

### IV. Linguagem de negócio maçônica
Interface e novos códigos usam **Potência** (tabela `prefeitura`), **Grão-Mestre** (`prefeito`), **Presidente** (`deputadoMestreId`). Termos antigos (Prefeitura/Prefeito/Deputado Mestre) são proibidos na UI. **Sem classes/graus** (MX/EN/CBCS) e **sem região** em Potência — não podem voltar em telas, filtros ou relatórios. Membro ↔ loja é **N:N** (`member_loja` com `dataInclusao`); situação é binária (ATIVO/INATIVO).

### V. Spec-first para features novas
Toda feature nova ou mudança significativa começa com spec em `specs/<modulo>/spec.md` (fluxo speckit: specify → plan → tasks → implement), revisada pelo dono do produto antes de código. Fix de uma linha não precisa de spec; precisa de critério de aceitação explícito.

### VI. Teste onde há regra
Regras de negócio na camada de dados (repositórios GPRB, serviços da API) exigem teste automatizado. Mudança em repositório sem teste associado deve justificar-se. Testes que tocam o modelo GPRB usam banco de teste dedicado ou seed controlado — nunca o banco real.

### VII. Clareza operacional
É um painel de trabalho: escaneabilidade, consistência e expectativas nativas vêm antes de expressão visual. Design system **HAZON** (`theme/static_src/tailwind.config.js`) é a única fonte de tokens; sem cores/estilos hardcoded fora dele.

### VIII. Simplicidade (YAGNI)
Começar simples. Nenhuma abstração, dependência ou tabela nova sem uso concreto agora. Métodos/tabelas mortos são removidos, não mantidos "para o futuro".

## Restrições Técnicas

- Django 5.2 (DTL + sessão) + FastAPI (`/api/v1`, JWT) no mesmo processo ASGI, porta 8888.
- Python 3.13 (`​.venv`), psycopg 3 (nunca psycopg2), PostgreSQL 17.
- Segurança fail-closed em produção: `DJANGO_SECRET_KEY`/`JWT_SECRET` obrigatórios, cookies Secure + HSTS sem `DJANGO_DEBUG=1`; bcrypt no modelo GPRB, `make_password` no Django; rate limit de login (5 tentativas).
- Idioma: interface em **português (Brasil)**; identificadores de código em inglês quando fizer sentido.
- Ambiente de dev é Windows nativo (sem Docker/WSL); restart manual do servidor (`--noreload`).

## Fluxo de Trabalho e Qualidade

1. **Baseline**: ler `specs/legacy/` (arquitetura, regras, banco, problemas conhecidos) antes de propor mudanças.
2. **Spec → Plan → Tasks → Implement** com revisão do humano entre fases (gates).
3. **Verificação obrigatória antes de "pronto"**: restart do servidor, E2E da rota tocada (login + telas afetadas) e `grep` de log sem erros novos.
4. **Atualizar documentação na mesma mudança**: `specs/legacy/` (se regra/banco mudou), `DOCS/PRD.md` (se produto mudou), `known-problems.md` (se problema foi resolvido/descoberto).
5. Backups `pg_dump -Fc` em `backups/` **antes** de qualquer DDL ou exclusão de dados.

## Governança

- Esta constitution supera práticas conflitantes. Emendas exigem documentação da mudança e aprovação do dono do produto.
- Conformidade verificada em toda revisão de PR/entrega: princípios I–IV e VII são critérios de bloqueio.
- Orientação de runtime: `specs/legacy/architecture.md` + `specs/legacy/business-rules.md`.

**Version**: 1.0.0 | **Ratified**: 2026-10-02 | **Last Amended**: 2026-10-02
