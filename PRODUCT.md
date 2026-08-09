# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

RedCRM serve três papéis dentro do modelo SaaS multi-tenant:

- **admin_saas** — operador da plataforma (dono do SaaS). Não pertence a nenhum tenant e por isso enxerga todos eles; cuida de provisionamento, clientes e saúde do produto.
- **dono** — dono do negócio cliente (um tenant). Acompanha pipeline, receita projetada e equipe.
- **recepção** — front-desk do tenant. Cadastra/atualiza contatos, move cartões no funil e cuida da agenda do dia.

## Product Purpose

CRM de vendas multi-tenant que organiza o pipeline comercial de pequenos negócios: captura de leads, funil kanban com drag & drop, ficha de contatos, agenda por dia útil e dashboard com KPIs (conversão por etapa, receita projetada ponderada, movimentações recentes). Existe para que negócios sem um CRM dedicado tenham, num só painel web, o controle do ciclo de venda — do interesse ao fechamento.

O sucesso significa: tenant vê seu pipeline inteiro atualizado num painel só, com receita projetada confiável, e a recepção consegue operar contatos/agenda sem treinamento pesado.

## Positioning

Um **núcleo de CRM, vários nichos**: as chaves de etapa e as categorias são fixas no banco, mas os rótulos se adaptam por vertical (saúde/estética, odontologia, imobiliária, educação, serviços, outro). Assim um mesmo produto atende clínicas, imobiliárias e escolas sem customização de código — apenas re-rotulando o funil para a linguagem do nicho. É essa camada de "tradução por nicho" que um CRM verticalizado não consegue copiar sem virar outro produto.

## Operating Context

- **Painel web** em Django 5.2 (templates DTL + Tailwind) na porta `8000`, autenticação por **sessão**.
- **API REST** em FastAPI (`/api/v1`) também na `8000`, autenticação por **JWT** (exclusiva da API).
- **Multi-tenant**: toda consulta web é escopada por `tenant_id` da sessão; o `admin_saas` (sem tenant) enxerga tudo.
- **Banco** PostgreSQL (`esferacrm`); o Django adota tabelas existentes via `Meta.db_table` + `migrate --fake-initial`.
- **Front legado** em HTML estático (`index.html`, `server.js` na porta `3001`) permanece só como referência.
- **Stack completa e dev commands** já definidos no `README.md` e em `systemdesign.md` (arquitetura em camadas route→service→repository).

## Capabilities and Constraints

- **Apps web**: `acesso` (login/logout, decorators `web_login_required`/`filtro_tenant`, context processor de sessão), `dashboard` (KPIs, timeline, conversão, funil, movimentações), `funil` (kanban com drag & drop, mover via POST), `contatos` (lista/busca, ficha, CRUD), `agendamentos` (agenda por dia útil a partir de hoje). `theme` é o app do django-tailwind.
- **Outros módulos no repo** (presença/estado a confirmar conforme evolução): `automacoes`, `campanhas`, `discador`, `emails`, `relatorios`, `tarefas`, `acordos`, `api/`.
- **Funil**: etapas fixas por chave — `interessado`, `avaliacao_agendada`, `avaliacao_feita`, `orcamento`, `fechado`, `perdido` — cada uma com cor fixa (`STAGES` em `core/dominio.py`). Nomes são re-rotulados por nicho.
- **Receita projetada**: `PESOS_ETAPA` pondera o valor por probabilidade de fechamento (10%→100%; `perdido`=0%).
- **Nichos** suportados (`_NICHO_NOMES`): `saude` (padrão), `odonto`, `imob`, `educacao`, `servicos`, `outro`.
- **Segmentos** (`SEGS`): estética, odontologia, dermatologia, fisioterapia, nutrição, psicologia, geral — cada um com cor.
- **Listas fixas** compartilhadas: `ORIGENS` (Instagram, Indicação, Google, WhatsApp, Site, Outro) e `PAGAMENTOS` (Particular, Convênio, Plano, Outro).
- **Convenção de dados**: campos vazios viram `'—'`; valor monetário default `0`; `updated_at` automático a cada escrita; IDs `SERIAL` + `TIMESTAMPTZ`.
- **Idioma**: código em inglês nos nomes de campo/rota quando fizer sentido; interface e mensagens em **português**.

## Brand Commitments

- **Nome do produto**: RedCRM.
- **Design system existente**: **HAZON** — tokens de cor únicos em `theme/static_src/tailwind.config.js` (paleta teal/night escura: `night`, `abyss`, `deep`, `surface`, `primary`, `accent`, `success`, etc.).
- **Tipografia**: `Manrope` (sans) e `Fraunces` (display).
- **Cores das etapas do funil** (`STAGES`) são fixas e compartilhadas entre nichos — parte da identidade visual do produto.

## Evidence on Hand

- `README.md` — arquitetura, setup, apps web, usuários de seed (admin@esferacrm.com, dona@aurora.com, ana@aurora.com).
- `systemdesign.md` — blueprint da arquitetura Django+FastAPI+PostgreSQL (camadas, contratos de API, padrão de testes).
- `core/dominio.py` — fonte da verdade de stages, pesos, nichos, segmentos, origens e pagamentos.
- `theme/static_src/tailwind.config.js` — tokens do design system HAZON.
- Seeds de exemplo: tenant "Aurora" (clínica), papéis admin_saas/dono/recepção.
- **Ausências que trabalho futuro não deve fabricar**: sem deploys/em produção confirmados, sem números de clientes reais, sem depoimentos/cases reais.

## Product Principles

1. **Multi-tenant first** — toda consulta é escopada por `tenant_id`; dados nunca vazam entre empresas. Decisões de produto que sacrificam esse isolamento são descartadas.
2. **Um núcleo, muitos nichos** — chaves e categorias são fixas; a diferenciação por vertical é só rótulo. Novo nicho = tradução, não novo código.
3. **O pipeline é a fonte da verdade comercial** — stages + `PESOS_ETAPA` produzem a receita projetada; qualquer feature de vendas parte do funil, não paralela a ele.
4. **Web e API compartilham o ORM/Django** — o painel web é a interface de uso diário; a API espelha o mesmo domínio, não é um produto separado.
5. **Clareza operacional sobre expressionismo** — é um painel de trabalho (modo Operate): escaneabilidade, consistência e expectativas nativas vêm antes de expressão visual.

## Accessibility & Inclusion

Interface em português (Brasil). Nenhum padrão de acessibilidade específico foi formalizado ainda; seguir boas práticas web (WCAG, contraste, navegação por teclado) ao tocar em UI é o piso esperado, não um diferencial.
