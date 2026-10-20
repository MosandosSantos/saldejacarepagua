# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

GPRBRCRM (nome de código) serve três papéis dentro do modelo SaaS multi-tenant:

- **admin_saas** — operador da plataforma (dono do SaaS). Não pertence a nenhum tenant e por isso enxerga todos eles; cuida de provisionamento, clientes e saúde do produto.
- **dono** — responsável pelo vale cliente (um tenant). Acompanha lojas, membros e equipe.
- **recepção / secretaria** — operação diária do tenant. Cadastra e atualiza membros e contatos, faz check-in e cuida da agenda e das tarefas.

## Product Purpose

Sistema de gestão para vales e lojas maçônicas, multi-tenant: cadastro de vales, lojas e membros, check-in com QR code, tarefas e comunicações, e a página institucional do vale (hero, calendário e a seção do Supremo Conselho, Grau 33). Existe para que cada vale organize sua vida administrativa e institucional num só painel web.

O produto começou como CRM de vendas. O CRM (funil, dashboard de receita, contatos comerciais) virou código legado e não é mais o foco.

O sucesso significa: cada tenant enxerga seus membros, lojas e agenda atualizados num painel só, e a secretaria opera o dia a dia sem treinamento pesado.

## Positioning

Um núcleo de gestão maçônica multi-tenant: cada vale opera isolado, com suas próprias lojas, membros e contatos, sobre a mesma base. O diferencial é unir gestão administrativa e a identidade institucional do rito (Grau 33) num só painel, sem depender de planilhas soltas.

## Operating Context

- **Painel web** em Django 5.2 (templates DTL + Tailwind) na porta `8000`, autenticação por **sessão**.
- **API REST** em FastAPI (`/api/v1`) também na `8000`, autenticação por **JWT** (exclusiva da API).
- **Multi-tenant**: toda consulta web é escopada por `tenant_id` da sessão; o `admin_saas` (sem tenant) enxerga tudo.
- **Módulo legado de CRM** (funil, dashboard de vendas, automações, campanhas, discador, emails, relatórios) permanece no repositório, mas não é prioridade para novas funções.
- **Banco** PostgreSQL (`gprbr`); o Django adota tabelas existentes via `Meta.db_table` + `migrate --fake-initial`.
- **Front legado** em HTML estático (`index.html`, `server.js` na porta `3001`) permanece só como referência.
- **Stack completa e dev commands** já definidos no `README.md` e em `systemdesign.md` (arquitetura em camadas route→service→repository).

## Capabilities and Constraints

- **Apps do produto atual**: `acesso` (login/logout, decorators `web_login_required`/`filtro_tenant`, context processor de sessão, página de login com hero, calendário e seção do Supremo), `contatos` (vales, lojas, membros, prefeituras e negócios), `tarefas` (tarefas, follow-ups e check-in com QR code). `theme` é o app do django-tailwind.
- **Apps legados de CRM**: `dashboard` (KPIs de pipeline e receita), `funil` (kanban com drag & drop), `automacoes`, `campanhas`, `discador`, `emails`, `relatorios`, `api/`. Manter funcionando, sem priorizar novas funções de vendas.
- **Funil (legado CRM)**: etapas fixas por chave — `interessado`, `avaliacao_agendada`, `avaliacao_feita`, `orcamento`, `fechado`, `perdido` — cada uma com cor fixa (`STAGES` em `core/dominio.py`). Nomes são re-rotulados por nicho.
- **Receita projetada**: `PESOS_ETAPA` pondera o valor por probabilidade de fechamento (10%→100%; `perdido`=0%).
- **Nichos** (legado CRM, `_NICHO_NOMES`): `saude` (padrão), `odonto`, `imob`, `educacao`, `servicos`, `outro`.
- **Segmentos** (legado CRM, `SEGS`): estética, odontologia, dermatologia, fisioterapia, nutrição, psicologia, geral — cada um com cor.
- **Listas fixas** (legado CRM): `ORIGENS` (Instagram, Indicação, Google, WhatsApp, Site, Outro) e `PAGAMENTOS` (Particular, Convênio, Plano, Outro).
- **Convenção de dados**: campos vazios viram `'—'`; valor monetário default `0`; `updated_at` automático a cada escrita; IDs `SERIAL` + `TIMESTAMPTZ`.
- **Idioma**: código em inglês nos nomes de campo/rota quando fizer sentido; interface e mensagens em **português**.

## Brand Commitments

- **Nome do produto**: GPRBRCRM.
- **Design system existente**: **HAZON** — tokens de cor únicos em `theme/static_src/tailwind.config.js` (paleta teal/night escura: `night`, `abyss`, `deep`, `surface`, `primary`, `accent`, `success`, etc.).
- **Tipografia**: `Manrope` (sans) e `Fraunces` (display).
- **Cores das etapas do funil** (`STAGES`, legado CRM) são fixas e compartilhadas entre nichos.
- **Identidade institucional do rito**: a página de login usa a paleta vinho e dourado da Maçonaria (medalhas e Supremo Conselho), que não segue o HAZON.

## Evidence on Hand

- `README.md` — arquitetura, setup, apps web, usuários de seed (admin@gprbr.com, dona@aurora.com, ana@aurora.com).
- `systemdesign.md` — blueprint da arquitetura Django+FastAPI+PostgreSQL (camadas, contratos de API, padrão de testes).
- `core/dominio.py` — fonte da verdade de stages, pesos, nichos, segmentos, origens e pagamentos (legado CRM).
- `contatos/models.py` e `contatos/views/vales.py` — vales, lojas e membros.
- `acesso/templates/acesso/login.html` — página de login com hero, calendário e seção do Supremo (Grau 33).
- `theme/static_src/tailwind.config.js` — tokens do design system HAZON.
- Seeds de exemplo: tenant "Aurora" (clínica), papéis admin_saas/dono/recepção.
- **Ausências que trabalho futuro não deve fabricar**: sem deploys/em produção confirmados, sem números de clientes reais, sem depoimentos/cases reais.

## Product Principles

1. **Multi-tenant first** — toda consulta é escopada por `tenant_id`; dados de um vale nunca vazam para outro. Decisões de produto que sacrificam esse isolamento são descartadas.
2. **Institucional e operacional** — a página pública respeita a identidade do rito; o painel é a ferramenta de trabalho da secretaria e do dono.
3. **Legado não define o produto** — código de CRM é mantido, mas novas funções partem da gestão de lojas e membros.
4. **Web e API compartilham o ORM/Django** — o painel web é a interface de uso diário; a API espelha o mesmo domínio, não é um produto separado.
5. **Clareza operacional sobre expressionismo** — é um painel de trabalho (modo Operate): escaneabilidade, consistência e expectativas nativas vêm antes de expressão visual.

## Accessibility & Inclusion

Interface em português (Brasil). Nenhum padrão de acessibilidade específico foi formalizado ainda; seguir boas práticas web (WCAG, contraste, navegação por teclado) ao tocar em UI é o piso esperado, não um diferencial.
