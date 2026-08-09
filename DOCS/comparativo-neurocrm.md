# Comparativo: neurocrm (modelo) × redcrm (nosso)

> **Propósito deste arquivo:** ser a fonte única de verdade da comparação entre o sistema
> modelo (pasta `neurocrm`, na verdade o template **wacrm** — CRM para WhatsApp) e o nosso
> **redcrm** (Django + FastAPI). Com ele, não precisamos reconsultar o projeto modelo para
> saber o que falta: aqui está o catálogo completo, o gap e o roadmap sugerido.
>
> Última atualização: 08/08/2026 · Projeto modelo: `C:\Users\mosan\Documents\Sistemas\crm\neurocrm`

---

## 1. Visão geral das duas stacks

| | **neurocrm (wacrm)** | **redcrm (nosso)** |
|---|---|---|
| Framework | Next.js 16 (App Router) + React 19 | Django 5 (templates DTL) + FastAPI (`api/v1`) |
| Banco | Supabase (Postgres + Auth + Realtime + Storage) | PostgreSQL (`esferacrm`) via Django ORM |
| Estilo | Tailwind 4 + shadcn/ui + Recharts | Tailwind (app `theme`) + SVG procinente |
| Autenticação | Supabase Auth (e-mail/senha) + sessão | Sessão Django (web) + JWT (API FastAPI) |
| Foco | CRM de **WhatsApp** (Meta Business API) | CRM de **funil de vendas por nicho** (saúde/odonto/imob…) |
| Testes | Vitest (dezenas de suites) + CI typecheck/build | Pytest (`teste/`) |
| Público | Time que atende WhatsApp num número só | Clínicas/negócios locais (modelo "aula a aula") |

**Resumo em uma frase:** o neurocrm é um CRM de *atendimento e disparo em WhatsApp*
(caixa de entrada, broadcasts, automações, fluxos) com time; o redcrm é um CRM de
*funil/leads/agenda* com visual premium e nichos configuráveis. O neurocrm é o
"motor de comunicação"; o redcrm é o "motor de vendas". Eles se complementam.

---

## 2. Catálogo completo do neurocrm (o que ele FAZ)

### 2.1 Autenticação e conta
- Cadastro (`/signup`), login (`/login`), recuperação de senha (`/forgot-password`).
- **Conta por time (account)**: todo cadastro cria uma conta; cada linha do banco é
  escopada à conta (`account_id`) e isolada por **RLS** (Row Level Security) no Postgres
  via função `is_account_member(account_id, min_role)`.
- **Convites por link**: `admin` gera link de convite com papel e validade; o convidado
  entra por `/join/[token]` (página de aceite) e vira membro; transferência de dono.
- **Papéis (roles)**: `owner` / `admin` / `agent` / `viewer`, com checagem por nível mínimo.
  E-mail de membros só aparece para admin+.

### 2.2 Caixa de entrada compartilhada (WhatsApp Business API / Meta)
- Conversas com status `open | pending | closed`, atribuição a agente,
  `last_message_text/at`, contador de não lidas.
- Mensagens com `sender_type` (cliente / agente / bot), `content_type`
  (texto, imagem, documento, áudio, vídeo, localização, template, interativo),
  `status` (sending/sent/delivered/read/failed), resposta/citação (`reply_to`),
  **reações**, **notas de voz** (MediaRecorder + opus), mídia (upload).
- Botões/listas interativas (`interactive_reply_id`) que alimentam os fluxos.
- Integração Meta: token do app criptografado (**AES-256-GCM**), `phone_number_id`
  único por conta, registro/verificação do número, webhook **verificado por HMAC**,
  API de mídia (download/resumable upload), envio via template.

### 2.3 Contatos
- Campos: telefone (normalizado p/ dedup por conta), nome, e-mail, empresa, avatar.
- **Tags** coloridas (M2M) e **campos personalizados** (nome + tipo + opções JSONB)
  com valores por contato.
- **Notas** por contato (com autor/data).
- **Importação CSV** com parse (encoding/delimitador), deduplicação por telefone/e-mail,
  mapeamento de colunas e modal de importação.

### 2.4 Funis (pipelines) e negócios
- **Deals** (negócios) como entidade própria, **ligados a conversas**, com valor e etapa.
- Kanban com **drag & drop** (dnd-kit), formulário de deal, **analytics do pipeline**
  (receita por etapa etc.) e configuração do pipeline (etapas/cores).

### 2.5 Broadcasts (disparo em massa via WhatsApp)
- Assistente em 4 passos: escolher template aprovado → selecionar público →
  personalizar variáveis por destinatário → agendar envio.
- Rastreio de **entrega e leitura** por destinatário (WAMID), contagens incrementais.

### 2.6 Automações no-code
- **Triggers**: mensagem recebida, novo contato, palavra-chave, agendamento (cron).
- **Passos**: enviar mensagem, condição (ramo sim/não), espera, adicionar tag, webhook.
- Builder visual, validação, contador de execuções, duplicar, templates prontos,
  engine própria + rota cron. (Tabelas: `automations`, `automation_steps` com
  `parent_step_id` + `branch`.)

### 2.7 Flows (builder visual de fluxos)
- Canvas de nós/arestas (React Flow/xyflow + dagre), engine própria, execuções com
  chave de idempotência `(account, contact)`, cron, ativação, templates, fallback,
  passos de mídia e envio via Meta. (Tabela `flow_runs` etc.)

### 2.8 Templates de mensagem WhatsApp
- Gerenciador de templates com integração Meta: sincronizar, submeter, status
  (aprovado/pendente/rejeitado), componentes (cabeçalho, corpo, botões), validadores.

### 2.9 Dashboard em tempo real
- Realtime (Supabase): métricas de volume diário, **tempo de resposta**,
  conversas por dia, **rosquinha do pipeline**, **feed de atividades** entre módulos,
  ações rápidas, total de não lidas.

### 2.10 Configurações (painel completo)
- Perfil (nome/avatar), troca de senha, **segurança e sessões ativas**,
  **aparência (tema claro/escuro)**, campos personalizados, tags, negócios,
  **membros (time)** + convites, **configuração do WhatsApp** (tokens, número, registro),
  gerenciador de templates.

### 2.11 Outros
- **i18n** (next-intl, dicionários de tradução), upload de mídia em storage
  (avatars, mídia de chat, mídia de flow — escopado por conta), rate limiting,
  headers de segurança (CSP, HSTS, etc.), token encryption, testes unitários amplos + CI.

---

## 3. Catálogo do redcrm (o que NÓS já temos)

### 3.1 Autenticação, time e configurações
- Login web por sessão (e-mail + senha com hash), logout, redirecionamentos.
- **Onboarding de nicho**: no 1º login, o admin da clínica escolhe o ramo do negócio,
  que re-rotula as etapas do funil (saúde, odonto, imobiliária, educação, serviços, outro).
- **Equipe**: admin da clínica convida por **link** (e-mail + papel); a pessoa aceita numa
  página pública `/convidar/<token>/` (nome + senha próprios) e entra direto como membro.
  Convites expiram em 7 dias, podem ser cancelados e o link pode ser copiado.
  Papéis: `admin_saas` (plataforma), `admin_company`, `operacional` e **`viewer`**
  (somente leitura — vê tudo, não cria/edita/exclui nada; sem drag no funil,
  sem botões de edição, sem importação; na API, toda escrita retorna 403).
- **Página de Configurações** (`/config/`): perfil (nome/e-mail), **troca de senha**
  (com senha atual), **tema claro/escuro** (por sessão, botão no header),
  **sessões ativas** (listar e encerrar remotamente, com dispositivo via User-Agent),
  equipe (convite por link) e convites pendentes.
- RBAC na web (`web_login_required`, `web_requer_admin`) e na API (`require_roles`).

### 3.2 Contatos (ficha rica)
- Modelo com **21+ campos**: nome, empresa, tel, e-mail, segmento, etapa, valor,
  procedimento, última consulta, origem, pagamento, nascimento, CPF, cidade, bairro,
  observações, **CNPJ, razão social, CNAE, endereço, responsável** (empresa).
- **Tags** coloridas por tenant; **notas** com autor/data (linha do tempo na ficha).
- **Campos personalizados** com 7 tipos (texto, número, data, telefone, e-mail,
  sim/não, lista), obrigatoriedade, ordem e gestão só por admin.
- **Importação CSV** completa: upload → mapeamento de colunas (com sugestão automática
  por apelidos em português) → relatório (importados/duplicados/erros), download de
  modelo CSV, dedup por telefone/e-mail, limite 5 MB.

### 3.3 Funil (kanban) e negócios
- 6 etapas com **chaves fixas e nomes por nicho**, colunas coloridas, contador e soma
  por coluna, cartões com segmento + valor, busca, total do funil.
- **Drag & drop sem recarregar** (fetch AJAX + resposta JSON): o cartão entra na coluna
  com animação e contadores/somas/total atualizam na hora; fallback por menu.
- **Deals como entidade própria** (`Negocio`): **vários negócios por contato** (1:N),
  com título, etapa, valor e um **negócio principal** (★ — alvo da edição rápida).
  Telas de novo/editar/excluir na ficha + tornar principal; histórico por negócio.
- Cartão do kanban = um **negócio** (não o contato).

### 3.4 Dashboard
- 4 KPIs (negócios ativos, valor no funil, fechados, taxa de conversão), gráfico de
  linha 30 dias (SVG), conversão por etapa, **funil 3D em SVG**, movimentações recentes.

### 3.5 Agenda
- Compromissos (call/reunião/demo) **agrupados por dia**, datas relativas a hoje
  (offset de dias úteis) — módulo que o neurocrm **não tem**.

### 3.6 API REST (FastAPI)
- `POST /api/v1/auth/login`, `GET /auth/me` (JWT); CRUD de contatos + mover etapa;
  agendamentos; usuários e tenants (somente `admin_saas`).
- **Rate limiting** (Fase D): janela deslizante em memória — 10 tentativas de
  login/min/IP e 300 req/min/IP global; responde `429` com `Retry-After`.
  Fail-safe: ativo por padrão (`DJANGO_RATE_LIMIT=1`), desligado nos testes via
  conftest; `DJANGO_TRUST_PROXY=1` troca a chave para o primeiro hop do
  `X-Forwarded-For` (use só atrás de proxy próprio).
- **Headers de segurança** (Fase D): `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, CSP `default-src 'none'` (+ CDN do Swagger p/ `/docs`) e HSTS
  em produção.

### 3.7 Multitenancy
- Modelo `Tenant` (empresa/clínica) com isolamento por `tenant_id` em todas as queries;
  `admin_saas` (sem tenant) enxerga tudo. Nicho salvo no tenant.

---

## 4. GAP — o que o neurocrm faz que o redcrm NÃO faz

> Ordenado do maior impacto para o menor. ✅ = já temos equivalente, ⚠️ = parcial, ❌ = não temos.

| # | Recurso do neurocrm | Situação | O que isso significa pra nós |
|---|---|---|---|
| 1 | **WhatsApp Business API (Meta)** — enviar/receber mensagens reais | ❌ | Requer app na Meta (tokens, webhook HMAC, `phone_number_id`). É a base de inbox, broadcasts, automações e flows. |
| 2 | **Caixa de entrada compartilhada (chat)** | ❌ | Conversas, mensagens, status (lida/entregue), atribuição a agente, não lidas, citações, reações, áudios. Não temos nenhum módulo de mensagens. |
| 3 | **Broadcasts** (disparo em massa com template aprovado + rastreio de entrega/leitura) | ❌ | Não temos disparos em massa nem rastreio. |
| 4 | **Automações no-code** (triggers + passos + cron + builder visual) | ❌ | Não temos engine de automação nem UI de builder. |
| 5 | **Flows** (builder de nós/arestas + engine + runs) | ❌ | Não temos editor visual de fluxos. |
| 6 | **Templates de mensagem WhatsApp** (gerenciar/submeter/sincronizar com Meta) | ❌ | Não temos. |
| 7 | **Deals como entidade própria** ligada a conversa/contato | ✅ | `Negocio` 1:N por contato (título, etapa, valor, principal), com histórico e analytics. Faltou só a ligação a conversa (vem com o WhatsApp). |
| 8 | **Drag & drop no kanban** | ✅ | HTML5 nativo + AJAX, sem recarregar a página, com fallback por menu. |
| 9 | **Time: convite por link, join, transferência de dono, 4 papéis** | ⚠️ | Convite por link + aceite + cancelamento ✅ e **papel `viewer`** (somente leitura) ✅. Falta só: **transferência de dono**. |
| 10 | **Dashboard em tempo real** (response time, atividade entre módulos, não lidas) | ⚠️ | Dashboard avançado ✅ (receita projetada, meta, tempo de fechamento, melhores negócios, atividade do time, velocidade por etapa, **auto-refresh 45s**). Faltam: response time e feed entre módulos (chegam com o WhatsApp). |
| 11 | **Página de Configurações** (perfil, senha, sessões, aparência claro/escuro, whatsapp, membros) | ⚠️ | ✅ perfil, senha, sessões ativas (listar/encerrar), tema claro/escuro, membros e convites. Falta só a aba **WhatsApp** (fase C). |
| 12 | **Upload de mídia/avatars** (storage escopado por conta) | ❌ | Não temos storage; perfil sem avatar. |
| 13 | **Segurança avançada**: RLS por conta, criptografia de tokens (AES-256-GCM), webhook HMAC, rate limiting, CSP/headers | ⚠️ | ✅ **Rate limiting** (login 10/min, global 300/min, 429+Retry-After, fail-safe), ✅ **headers de segurança** (CSP, HSTS, nosniff, frame, referrer — web e API) e ✅ **criptografia AES-256-GCM** (`core/segredos.py`, pronta p/ tokens Meta). Faltam: RLS do Postgres (temos isolamento por `tenant_id` no ORM) e webhook HMAC (chegam com o WhatsApp). |
| 14 | **Analytics do pipeline** (receita por etapa, projeções) | ✅ | Receita por etapa, ticket médio, origens, segmentos, **receita projetada ponderada**, tempo médio de fechamento e velocidade por etapa. |
| 15 | **Métricas de tempo de resposta** | ❌ | Não medimos. |
| 16 | **i18n (multi-idioma)** | ⚠️ | Só PT-BR — para o nosso público, provavelmente ok manter assim. |
| 17 | **Tema claro/escuro** | ✅ | Toggle no header (🌙/☀️), preferência por sessão; páginas públicas seguem sempre escuras. |
| 18 | **Realtime** (atualização ao vivo entre abas/usuários) | ❌ | Sem websockets/realtime. |

---

## 5. O que o redcrm tem que o neurocrm NÃO tem (nossos diferenciais)

| Recurso | Por que é nosso diferencial |
|---|---|
| **Agenda de compromissos** (call/reunião/demo por dia) | O neurocrm **não tem agenda**. É um módulo que só nós temos. |
| **Nichos configuráveis por tenant** (funil re-rotulado: saúde, odonto, imobiliária…) | O neurocrm tem pipeline configurável, mas não re-rotula o funil inteiro pelo ramo do cliente. |
| **Ficha de contato rica para saúde** (procedimento, última consulta, pagamento, origem, CPF, CNPJ, CNAE, endereço…) | Campos de negócio prontos para clínicas/consultórios, sem depender de custom fields. |
| **Onboarding de nicho no 1º login** | Experiência guiada que o neurocrm não tem. |
| **API REST própria (FastAPI) com CRUD completo + JWT** | O neurocrm usa rotas Next + cliente Supabase; temos uma API formal. |
| **Importador CSV com mapeamento automático em PT-BR** | Sugestão de colunas por apelidos em português + modelo CSV + relatório. |

---

## 6. Mapa conceitual 1:1 (para consulta rápida)

| Conceito | neurocrm | redcrm |
|---|---|---|
| Pessoa que compra | `Contact` (telefone normalizado) | `Contato` (sem normalização de telefone) |
| Etiqueta | `Tag` + `ContactTag` | `Tag` (M2M) |
| Campo extra | `CustomField` + `ContactCustomValue` | `CampoPersonalizado` + `ValorCampoPersonalizado` |
| Anotação | `ContactNote` | `Nota` (com autor) |
| Negócio | `Deal` (entidade própria, ligada a conversa) | `Negocio` (entidade própria, **1:N** por contato, flag `principal`) |
| Conversa | `Conversation` + `Message` | ❌ não existe |
| Etapas | configuráveis no pipeline | `core/dominio.py` (chaves fixas, nomes por nicho) |
| Time | `Account` + `AccountMember` + `AccountInvitation` (4 papéis) | `Tenant` + `Usuario` + `Convite` (4 papéis: admin_saas, admin_company, operacional, viewer) |
| Automação | `Automation` + `AutomationStep` | ❌ não existe |
| Fluxo | `Flow` + `FlowRun` | ❌ não existe |
| Disparo | `Broadcast` + `BroadcastRecipient` | ❌ não existe |
| Template WhatsApp | `MessageTemplate` (integração Meta) | ❌ não existe |
| Agenda | ❌ não existe | `Agendamento` (offset de dias úteis) |

---

## 7. Roadmap sugerido (para continuarmos o desenvolvimento)

> **Ordem acordada com o cliente (06/08/2026):**
> 1º **Funil de vendas** **OU** **Time & configurações** (a decidir) ·
> 2º o outro deles ·
> 3º **Dashboard** ·
> 4º **WhatsApp** (último — exige conta Meta Business) ·
> 5º **Redes sociais** e **carrinho de compras** (sprints futuros anotados — ver §8).
>
> As fases abaixo são descrições independentes; a ordem de execução é a acordada acima.

### Fase A — Funil e vendas (menor esforço, maior valor pro curso) ✅ CONCLUÍDA (06/08/2026)
1. ✅ **Drag & drop no kanban** (Aula 4 do curso) — cartão arrasta e solta **sem recarregar a página** (fetch AJAX + resposta JSON do `funil:mover`), com destaque visual na coluna, animação de entrada, atualização instantânea de contadores/somas/total e fallback por menu. (`funil/templates/funil/kanban.html`, `funil/views.py`)
2. ⏳ **Deals como entidade própria** (opcional) — ficou para depois; mantivemos `stage + valor` no contato, mas agora com **histórico de etapas** (`Movimentacao`).
3. ✅ **Analytics do funil** — novo painel "Análise do funil" no dashboard: receita por etapa (barras), ticket médio, origens dos contatos e valor por segmento. (`dashboard/views.py`, `dashboard/partials/_analise.html`)
4. ✅ **Normalização de telefone** — campo `tel_normalizado` (dígitos) preenchido no save + migração de backfill; formulário **bloqueia telefone duplicado** no tenant; importador já deduplica por dígitos. (`contatos/models.py`, `contatos/forms.py`, migração `0006`)

> **Bônus da Fase A:** movimentações recentes do dashboard agora mostram **quem moveu e para qual etapa** (com fallback para os últimos contatos quando ainda não há histórico); a ficha do contato ganhou a seção **Histórico de etapas** (de → para · autor · data).

### Fase A1 — Deals como entidade própria + múltiplos negócios por contato ✅ CONCLUÍDA (06/08/2026)
- ✅ **Entidade `Negocio` (deal)** — novo modelo 1:1 com `Contato` com `titulo`, `stage`, `valor`, `tenant`, `created_at` e `updated_at` próprios (migração `0007` com backfill dos contatos existentes).
- ✅ `stage`/`valor` **removidos do Contato** (ficaram properties de leitura por compatibilidade); todo o código (views, importador, API, dashboard, funil) opera sobre o negócio.
- ✅ **Histórico ligado ao negócio** — `Movimentacao.negocio` (era `contato`); funil, formulário web, importador e API gravam o histórico do deal.
- ✅ **Analytics por negócio** — timeline do dashboard agora usa `negocio.updated_at` (mover etapa atualiza); receita por etapa, ticket médio, origens e segmentos calculados sobre negócios.
- ✅ 105 testes passando (incl. API cria negócio e fluxo web cria/edita negócio com histórico).
- ✅ **Multi-deal (1:N)**: `Negocio.contato` virou FK (migração `0008` com backfill da flag `principal`);
  ficha com **painel de negócios** (novo/editar/excluir/★ principal); funil move **o negócio**;
  API e views com `prefetch_related('negocios')` (sem N+1); `tornar_principal()` marca/desmarca.
- ▶️ **Futuro (fora de escopo agora):** projeções de receita por negócio.

### Fase B — Time e configurações ✅ CONCLUÍDA (06/08/2026)
5. ✅ **Página de Configurações** (`/config/`) — perfil (nome/e-mail), **troca de senha**,
   **tema claro/escuro** (por sessão), **sessões ativas** (listar/encerrar, com dispositivo),
   equipe e convites. (`acesso/views.py`, `acesso/templates/acesso/config.html`)
6. ✅ **Convite por link** — admin gera link (e-mail + papel, expira em 7 dias); a pessoa
   aceita em `/convidar/<token>/` (nome + senha) e entra direto como membro. Cancelamento
   pelo admin e lista de pendentes com botão de copiar link.
   (`Convite` modelo + migração `0003`; `convidar.html`)
7. ✅ **Sessões ativas** — lista as sessões do usuário na tabela `django_session` (sessão
   atual destacada) e encerra remotamente.
8. ✅ Nav "Configurações" no header substituiu "Equipe" (a rota `/equipe/` antiga continua
   funcionando para não quebrar links).
9. ✅ **Papel `viewer` (somente leitura)** — novo papel de tenant: enxerga dashboard,
   funil, contatos, ficha e agenda, mas não cria/edita/exclui nada (web + API), sem
   drag & drop no kanban, sem importação e sem gestão de equipe; pode alterar apenas
   o próprio perfil/senha/tema/sessões. (`ROLE_VIEWER`, `web_requer_edicao`,
   `require_edicao`, opção nos convites; seed com `laura@aurora.com` / `senha123`)
   De quebra, corrigimos o **link do cartão do kanban**, que apontava para o id do
   negócio em vez do contato.

### Fase C1 — Dashboard avançado ✅ CONCLUÍDA (06/08/2026)
1. ✅ **Receita projetada** — pipeline ponderado por etapa (`PESOS_ETAPA` em `core/dominio.py`):
   Interessado 10% → Avaliação agendada 25% → Avaliação feita 40% → Orçamento 65% → Fechado 100%.
   KPI com anel mostrando quanto do potencial em aberto virará receita.
2. ✅ **Meta do mês** — campo `meta_mensal` no `Tenant` (migração `0004`), configurável em
   `/config/#metas` (admin da clínica); KPI com barra de progresso (fechados do mês vs meta,
   cap visual em 100% e % real no chip).
3. ✅ **Tempo médio de fechamento** — média de dias do `created_at` ao fechamento (mês atual).
4. ✅ **Melhores negócios** — top 5 em aberto por valor, com barra relativa e etapa.
5. ✅ **Atividade do time** — movimentações + notas por membro nos últimos 30 dias (avatar, contagens).
6. ✅ **Velocidade média por etapa** — tempo que os negócios passam em cada etapa (do histórico).
7. ✅ **Auto-refresh (quase-realtime)** — endpoint `GET /dashboard/dados/` (JSON) + polling a cada
   45s atualiza KPIs, anel e barras sem recarregar; botão "Atualizar" manual + timestamp.
8. ✅ KPIs com **badges reais** (novos no mês, últimos 30d, valor fechado) e "Fechados no mês"
   agora com escopo mensal correto.
> 157+ testes passando (12 novos). Revisão aplicada: `data-kpi` da meta alinhado ao JSON,
> datetimes aware (sem warnings), barra da meta capada em 100%.

### Fase C — Comunicação (WhatsApp) — a grande fronteira ⏸️ PLANEJADO (06/08/2026)
8. **Integração WhatsApp** (tokens, webhook, número) → base para tudo abaixo.
9. **Caixa de entrada compartilhada** (chat) com mensagens/status/atribuição.
10. **Templates de mensagem** + **Broadcasts** com rastreio.
11. **Automações no-code** e **Flows** (builder visual) — motores de regra e fluxo.

> **Planejamento feito (06/08/2026) — implementação ADIADA.** Decisão de provedor
> **pendente** — candidatos pesquisados:
>
> | Opção | Custo | Prós | Contras |
> |---|---|---|---|
> | **Meta Cloud API (oficial)** | R$ 0 mensal; paga por conversa (US$0,03–0,10, BR) | Sem mensalidade; fundação já pronta no código (`core/segredos.py` AES-256-GCM p/ token, webhook HMAC, `phone_number_id`) | Exige conta Meta Business + **verificação do negócio** (dias) + número dedicado |
> | **Evolution API (self-hosted)** | Gratuito (open source, Baileys) | Sem verificação Meta; QR code; muito usado por pequenos negócios BR | Protocolo não oficial (risco de bloqueio/ban do número); você mantém o servidor |
> | **360dialog (BSP)** | ~US$49/mês + msg em R$ | Suporte BR, onboarding facilitado | Mensalidade |
> | **Z-API (BSP BR)** | Plano mensal em R$ | Cobrança em R$, suporte BR | Mensalidade |
> | **Twilio** | paga por conversa (USD) | Robusto, multicanal | Mais caro p/ esse nicho, menos BR-focused |
>
> **Arquitetura prevista (quando decidirmos):** C1 conexão (token cifrado, registro do
> número, webhook + desafio + HMAC, tabelas `Conversa`/`Mensagem` escopadas por tenant) ·
> C2 caixa de entrada (status lida/entregue, mark-as-read, atribuição a agente, não lidas,
> mídia, janela 24h) · C3 templates aprovados + broadcasts com rastreio (WAMID) ·
> C4 automações no-code + flows.
> **Pré-requisitos do cliente:** conta Meta Business + verificação (Meta oficial/Evolution não)
> + número dedicado + cartão p/ mensagens. A redecidir depois — por ora, só planejamento.

### Fase D — Qualidade e segurança ✅ CONCLUÍDA (06/08/2026)
12. ✅ **Rate limiting na API** — janela deslizante em memória (`api/v1/rate_limit.py`),
    login 10 req/min/IP e global 300 req/min/IP, `429` com `Retry-After`. **Fail-safe**:
    ativo por padrão (`DJANGO_RATE_LIMIT=1`); os testes desligam via `conftest.py`
    (o ambiente de testes do Django força `DEBUG=False`, então não usamos DEBUG como gate).
    `DJANGO_TRUST_PROXY=1` usa o primeiro hop do `X-Forwarded-For` (anti-spoofing por padrão).
13. ✅ **Headers de segurança** — web (Django): CSP completo (`CSP_DIRETIVAS` em settings +
    `core/middleware.py`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
    `Referrer-Policy: same-origin`, cookies `HttpOnly`/`SameSite=Lax` (incl. CSRF — o JS
    lê o token do DOM), HSTS + redirect SSL em produção. API (FastAPI): CSP `default-src 'none'`
    (+ CDN do Swagger), nosniff, frame, referrer e HSTS. CSP libera fonts do Google e a
    BrasilAPI (CNPJ). *Nota:* `script-src` mantém `'unsafe-inline'` por causa dos scripts
    inline das telas — trocar por nonces quando migrarmos para front com bundle.
14. ✅ **Criptografia de segredos** — `core/segredos.py`: AES-256-GCM (`cryptography`),
    chave 32 bytes derivada de `CRYPTO_KEY`/`SECRET_KEY`, nonce único por operação,
    formato `v1:<base64>`, adulteração detectada. Pronta para cifrar tokens do WhatsApp.
15. ✅ **CI** — `.github/workflows/ci.yml`: Python 3.13 + Postgres 16 (serviço), roda
    `manage.py check`, `makemigrations --check --dry-run` e a suíte pytest em todo push/PR.
16. ✅ **Cobertura de testes** — `teste/test_fase_d_seguranca.py` (19 testes): roundtrip e
    tamper da cripto, headers web/API, HSTS dev×prod, 429 no login, fail-safe padrão,
    chave por IP vs proxy. **176 testes no total**.
> ▶️ **Realtime (WebSockets)** fica para depois: o dashboard já tem auto-refresh (polling
> 45s) e o realtime completo chega junto com a caixa de entrada do WhatsApp.
> ⚠️ **Deploy:** ative `DJANGO_RATE_LIMIT=1` e defina `CRYPTO_KEY` forte; atrás de proxy
> que termina o TLS, ajuste `SECURE_PROXY_SSL_HEADER` e `DJANGO_TRUST_PROXY=1`.

---

## 8. Sprints futuros (ANOTADOS — não trabalhar agora)

> Registro de memória de produto, sem implementação. O cliente pediu para apenas anotar.

| # | Sprint futuro | Escopo previsto | Observação |
|---|---|---|---|
| 1 | **Redes sociais — postagem** | Postar conteúdo automaticamente nas redes sociais (agendamento/publisher) | Vem depois do WhatsApp |
| 2 | **Redes sociais — captação de leads** | Capturar leads originados de redes sociais (formulários, comentários, DMs) | Vem depois da postagem |
| 3 | **E-commerce — resgate de carrinho** | Recuperar carrinhos de compra abandonados (lembretes, mensagens automáticas) | Vem depois da captação |

> Os 3 sprints futuros formam a sequência natural depois da fase de comunicação: primeiro o WhatsApp
> (atendimento), depois postar nas redes (atração), depois captar leads (conversão) e por fim resgatar
> carrinhos (receita). Nada disso é para ser construído agora — apenas registrado.

---

## 9b. Comparativo: top-10 CRMs do mercado × redcrm (pesquisa 06/08/2026)

> Pesquisa por solicitação do cliente: *"o que os 10 melhores CRMs do mercado têm que
> nós não (excluindo WhatsApp)"*. Analisados: Salesforce Sales Cloud, HubSpot CRM,
> Pipedrive, Zoho CRM, Freshsales, monday Sales CRM, Zendesk Sell, Bitrix24, Agile CRM,
> Insightly, Copper, Odoo.

### Checklist de recursos

| Recurso | Top CRMs | Nós (redcrm) |
|---|---|---|
| Contatos ricos, tags, notas, campos customizados | ✅ todos | ✅ temos (21+ campos) |
| Pipeline/kanban com drag & drop | ✅ todos | ✅ temos (AJAX sem reload) |
| Vários negócios por contato | ✅ | ✅ temos (Negocio 1:N + principal) |
| Dashboard + receita projetada + meta | ✅ | ✅ temos (parcial: falta previsão por vendedor) |
| **Relatórios gerenciais (KPIs de cobrança + filtros + exportação)** | ✅ | ✅ temos (Fase S — `/relatorios/` com base, CPC, retornos, acordos, valor recuperado, produtividade por operador, filtros hoje/7d/30d/mês e por operador, gráficos da série diária, CSV+PDF) |
| Agenda/compromissos | ✅ | ✅ temos (e neurocrm não tem — diferencial) |
| Time: papéis, convites, dono | ✅ | ✅ temos (4 papéis + transferência de dono) |
| **Tarefas & lembretes (follow-ups)** | ✅ todos | ✅ temos (Fase G) |
| **E-mail: integração Gmail/Outlook, tracking, templates, campanhas** | ✅ todos | ❌ **não temos** |
| **Automação no-code (regras/triggers/ações)** | ✅ todos | ❌ **não temos** |
| **Formulários de captura (web forms → lead automático)** | ✅ todos | ✅ temos (Fase H) |
| **Pipeline configurável (etapas/cores próprias, múltiplos)** | ✅ todos | ✅ temos (Fase F) |
| **Lead scoring** | ✅ maioria | ✅ temos (Fase J — origem/segmento/interação, badge 🔥 e ordenação) |
| **Metas/cotas por vendedor** | ✅ | ✅ temos (Fase J — MetaVendedor + dashboard de atingimento) |
| **Exportação de dados (CSV/PDF)** | ✅ | ✅ CSV (Fase E) + **orçamento em PDF** (Fase J) + **relatório gerencial CSV/PDF** (Fase S) |
| **Orçamento/proposta em PDF** | ✅ maioria | ✅ temos (Fase J — reportlab, parcelas, assinaturas) |
| **Alerta de negócio estagnado (rotten deals)** | ✅ | ❌ **não temos** (dá pra derivar do tempo por etapa) |
| Telefonia (click-to-call/gravação) | ✅ maioria | ❌ |
| Chat web ao vivo no site | ✅ maioria | ❌ |
| IA (escrita de e-mail, resumo, scoring) | ✅ todos (2025+) | ❌ |
| Integrações/marketplace/webhooks outbound | ✅ todos | ⚠️ API própria, sem webhooks |
| Mobile nativo (iOS/Android) | ✅ todos | ❌ (responsivo web) |
| Multi-moeda / catálogo de serviços | ✅ | ❌ |
| E-commerce/checkout | ⚠️ Bitrix24 | ❌ (sprint futuro anotado) |

### Fase E — Paridade com o mercado (RODADA 1 ✅ 06/08/2026)

Executados (solicitados pelo cliente):
1. ✅ **Exportação de dados (CSV)** — `/contatos/exportar/` (contatos com tags + negócio principal) e
   `/contatos/exportar/negocios/` (deals), BOM utf-8 (Excel), `;` como separador, etapa com rótulo do
   nicho e **proteção contra CSV injection** (`= + - @` viram texto). Botões na lista e no funil.
2. ✅ **Alerta de negócio estagnado** — seção ⏳ no kanban com os negócios abertos parados há +X dias
   (3/7/15/30, padrão 7), com etapa, valor e link pra ficha — recuperação de negócios mofando.
3. ✅ **E-mail marketing básico** — novo app `emails/` (nav "E-mail"):
   - **Modelos** (`ModeloEmail`) com placeholders `{{nome}} {{empresa}} {{procedimento}} {{valor}} {{telefone}} {{email}}`;
   - **Envio individual** na ficha do contato (seletor de modelo → dispara e volta com confirmação);
   - **Campanha em massa** (`/emails/campanha/`): escolhe modelo + filtro por segmento, pré-visualiza
     o público e dispara (só contatos com e-mail real — o default `'—'` do campo é tratado como vazio);
   - **Rastreio de abertura** por pixel 1x1 (`/emails/aberto/<uuid>/`, público mas token de 128 bits)
     + histórico `EmailEnviado` (status pendente/enviado/simulado/erro);
   - **Modo simulação** sem SMTP: registra tudo sem enviar; com `EMAIL_HOST`/`EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD`
     no `.env` (settings `EMAIL_*`), envia de verdade via `django.core.mail`.
   - Segurança: isolamento por tenant em todas as rotas; `admin_saas` (sem tenant) não quebra o módulo.
> **198 testes passando** (+16: export, estagnados, templates, envio individual, campanha, pixel, CSV injection).

### Fase F — Pipeline configurável por tenant ✅ CONCLUÍDA (06/08/2026)

Executado (item 2 da rodada):
1. ✅ **Etapas do funil por tenant** — novo modelo `EtapaFunil` (`funil/models.py`, migração
   `funil/0001`): cada clínica tem o próprio pipeline (nome, cor, ordem e **probabilidade de
   fechamento**), com backfill das etapas do nicho para os tenants existentes. Quem ainda não
   tem nicho é semeado no **onboarding** com o nicho escolhido (`adotar_nicho` — corrige também
   tenants que receberam rótulos do nicho padrão num backfill antigo, sem tocar etapas customizadas).
2. ✅ **Gestão em `/config/#etapas`** (admin da clínica) — criar etapa (nome/cor/probabilidade/ordem),
   renomear/recolorir/reordenar e excluir, com guardas: **`fechado`/`perdido` são etapas de sistema**
   (renomeáveis, não excluíveis — o dashboard depende delas) e **etapa com negócios não pode ser
   excluída**. Link ⚙️ **Etapas** no kanban.
3. ✅ **Integração em todo o sistema** — funil (kanban + mover), **dashboard** (a receita projetada
   usa o peso da etapa do tenant), formulários de contato/negócio, ficha, exportação CSV (rótulos
   do tenant) e importador (reconhece nomes customizados) usam o pipeline do tenant; `admin_saas`
   segue com as etapas padrão do nicho.
4. ✅ **API valida a etapa** — criar/atualizar/mover com etapa fora do pipeline do tenant retorna `400`
   (antes aceitava qualquer string — um negócio podia sumir do funil numa etapa excluída).
5. ✅ **216 testes passando** (+18: fallback do nicho, semeação idempotente, onboarding, renomear/criar/
   excluir com guardas, isolamento entre tenants, mover p/ etapa customizada, formulários, receita
   ponderada, importador e API).

### Fase G — Tarefas & lembretes (follow-ups) ✅ CONCLUÍDA (06/08/2026)

Executado (item 1 da rodada):
1. ✅ **Novo app `tarefas/`** — modelo `Tarefa` (migração `0001`): título, descrição, **contato**
   (FK), **responsável** (FK, padrão quem criou), **prioridade** (baixa/média/alta), **vencimento**
   e status (concluída + quando). Tudo escopado por tenant.
2. ✅ **Página `/tarefas/`** — captura rápida no topo (título + contato + responsável + prioridade +
   vencimento), busca por texto/contato e **seções de lembrete**: ⏰ Atrasadas · 📌 Para hoje ·
   🗓️ Próximas · Sem data · ✅ Concluídas (recentes). Concluir/reabrir por checkbox, editar e
   excluir (só admin).
3. ✅ **Lembretes em todo o sistema** — **badge vermelho no header** (nav "Tarefas") com a contagem
   de atrasadas em todas as páginas; **alerta "📌 Tarefas & lembretes"** no topo do dashboard com
   atrasadas + de hoje; **seção Tarefas na ficha do contato** com criação rápida de follow-up.
4. ✅ **Segurança** — viewer não cria/conclui/edita (só vê); excluir só admin; contato/responsável
   validados contra o tenant (POST manipulado não cria referência cruzada entre clínicas);
   `_voltar` usa `url_has_allowed_host_and_scheme` (anti-open-redirect); badge calculado numa
   única query agregada.
5. ✅ **231 testes passando** (+15: CRUD, seções, permissões, isolamento, ficha, badge, alerta do
   dashboard, referência cruzada e open redirect).

### Fase H — Formulário público de captura de lead ✅ CONCLUÍDA (06/08/2026)

Executado (item 1 da rodada):
1. ✅ **Link público por tenant** — `Tenant` ganhou `token_captura` (token_urlsafe(18), único),
   `origem_captura` (Site/Instagram/WhatsApp) e `captura_ativa` (migração `0006`); o link
   `/captura/<token>/` é gerado sob demanda em `Configurações → Captura de lead` (com botão
   "Gerar novo" e copiar link) e funciona **sem login** — quem preenche vira **contato + negócio**
   na **primeira etapa do pipeline** do tenant.
2. ✅ **Proteções** — **honeypot** anti-robô (campo invisível `website`; robô recebe sucesso sem gravar),
   **rate limit por IP** (5 envios válidos/hora via cache; erros de digitação NÃO consomem o limite)
   e **deduplicação por telefone normalizado** (`tel_normalizado`): mesmo telefone no mesmo tenant
   atualiza o contato existente e registra um novo negócio — sem contato duplicado.
3. ✅ **Visual premium** — página pública com card glass (mesmo estilo do login/convite), campos
   nome/telefone/e-mail/área de interesse/como podemos ajudar, estados de sucesso e de
   formulário desativado.
4. ✅ **Configuração só para admin da clínica** — seção "Captura de lead" em `/config/`
   (origem, ativo/desativado, link copiável, gerar novo token); operacional não vê a seção.
5. ✅ **245 testes passando** (+14: abre sem login, cria contato/negócio na 1ª etapa, origem
   configurada, validações, honeypot, token 404, desativado, rate limit, dedup, erros não
   consomem limite, config admin×operacional).

### Fase I — Automações no-code (regras) ✅ CONCLUÍDA (07/08/2026)

Executado (item 1 da rodada):
1. ✅ **Novo app `automacoes/`** — modelos `Automacao` (gatilho + parâmetros JSON + ativa),
   `PassoAutomacao` (ações em ordem) e `RegistroExecucao` (log ok/erro com contato/negócio).
2. ✅ **4 gatilhos**: `contato_criado` (novo cadastro), `negocio_criado`, `negocio_movido`
   (com filtro opcional **por etapa de destino** do pipeline do tenant) e `negocio_estagnado`
   (abertos parados há X dias, com filtro opcional de etapa).
3. ✅ **4 ações** (em ordem, com placeholders `{{nome}} {{empresa}} {{valor}} {{etapa}} {{origem}}…`):
   criar **tarefa** (título, prioridade, vence em N dias, responsável), adicionar **nota**
   (com autor), adicionar **tag** e enviar **e-mail** (usando `ModeloEmail` existente, com
   pixel de abertura e modo simulação sem SMTP).
4. ✅ **Motor central** (`automacoes/engine.py` `disparar()`): só automações **ativas do mesmo
   tenant**; erro numa ação não derruba o fluxo (vira status `erro` no log); contador de
   execuções + `ultima_execucao`. `executar_estagnados()` + comando `verificar_estagnados`
   (agendável via Task Scheduler/cron) + botão "⏳ Verificar estagnados agora" na tela.
5. ✅ **Hooks em todos os pontos de evento** — formulário web (`/contatos/novo/`),
   edição com mudança de etapa, novos negócios na ficha, kanban (`/funil/<id>/mover/`),
   captura pública, importador CSV e API FastAPI (criar/atualizar/mover).
6. ✅ **UI em `/automacoes/`** — cards com gatilho (cor por tipo), ações, contador e toggle
   ativa; formulário no-code com builder de passos (JS) e campos dependentes do gatilho;
   duplicar (cópia nasce desativada), testar (roda contra o contato mais recente) e
   execuções recentes na lista. Nav "⚡ Automações" no header.
7. ✅ **Segurança** — gestão restrita ao admin (`web_requer_admin`); viewer/operacional só
   veem a lista; responsável de outra clínica descartado na ação; parâmetros JSON validados
   no servidor; tudo escopado por tenant.
8. ✅ **270 testes passando** (+25: CRUD web, gatilhos, filtro por etapa, inativa, placeholders,
   ações tarefa/nota/tag/e-mail, isolamento entre tenants, estagnados via comando e botão,
   permissões viewer/operacional, captura, importador, API e edição).

### Fase J — Lead scoring + orçamento em PDF + metas por vendedor ✅ CONCLUÍDA (07/08/2026)

Executado (itens 1–3 da rodada, em uma tacada só):

**1. Lead scoring (pontuação automática de contatos)**
- ✅ Novo módulo `contatos/scoring.py` + campo `Contato.lead_score` (migração `0009`).
- ✅ Pontos por **origem** (Indicação 10 · Google 8 · WhatsApp 7 · Instagram 6 · Site 4 · Outro 2),
  **segmento** (odonto 8 … geral 3), e-mail/telefone preenchidos, **notas** (3 pts, cap 15),
  **movimentações** (4 pts, cap 20), **valor** no negócio (+10) e **etapa** (fechado 20 → perdido -8).
- ✅ **Níveis quente (≥40) / morno (≥20) / frio** com badge colorido 🔥 na ficha, na lista e no
  cartão do kanban; **ordenação por prioridade** (`/contatos/?ord=score`).
- ✅ **Hooks em todos os pontos de evento** — formulário web, edição, negócios, notas, kanban,
  captura pública, importador e API (criar/atualizar/mover) recalculam o score persistido.

**2. Orçamento / proposta em PDF**
- ✅ `contatos/orcamento.py` (reportlab): cabeçalho da clínica, dados do cliente, descrição,
  tabela de valores, **condições de pagamento (1x/2x/3x com a última parcela fechando o total)**,
  observações, assinaturas e rodapé com validade de 7 dias.
- ✅ Rota `/contatos/<pk>/negocios/<id>/orcamento/` + botão 📄 na ficha (qualquer papel logado
  pode baixar; escopado por contato+tenant — 404 fora da clínica).
- ✅ **Escaping XML + Latin-1** (`_p`): nomes com `&`/`<` não quebram o PDF (bug crítico
  corrigido na revisão). reportlab adicionado ao `requirements.txt`.

**3. Metas por vendedor**
- ✅ `Negocio.responsavel` (FK Usuario, migração `0009`) + model `MetaVendedor`
  (migração `acesso/0007`, única por usuário+mês).
- ✅ **Config em `/config/#metas-vendedores`** (admin): metas por membro com navegação
  entre meses; apagar valor remove a meta.
- ✅ **Select "Vendedor responsável" no formulário de negócio**; contato novo fica sob
  responsabilidade de quem cadastrou; select valida contra o tenant (sem referência cruzada).
- ✅ **Dashboard**: seção "Metas dos vendedores" com vendido do mês (fechados por responsável),
  % de atingimento, barra colorida e selo "✓ meta batida" (≥100%); isolada por tenant.
- ✅ **291 testes passando** (+21 novos) — e de quebra corrigimos uma regressão da Fase I:
  o bloco de criação na **captura pública** tinha ficado fora do guarda de validação
  (`UnboundLocalError` em POSTs inválidos) — 4 testes da Fase H voltaram a passar.

### Fase K — Timestamps padronizados (§7.6 do PRD HAZON) ✅ CONCLUÍDA (08/08/2026)

Executado por solicitação do cliente (PRD HAZON — §7.6: "todos os modelos com `created_at` e `updated_at`"):
1. ✅ **Padronização em todos os 22 modelos** (7 apps: acesso, contatos, funil, tarefas, emails,
   automacoes, agendamentos) — todo modelo agora tem `created_at` (auto_now_add) e `updated_at`
   (auto_now). Antes era misturado: `created_at` só em Tenant/Usuario, `criado_em`/`criada_em` na
   maioria dos modelos e `atualizada_em` em Automacao; vários não tinham `updated_at`.
2. ✅ **Renames via RenameField** (migrações: acesso/0008, contatos/0010, funil/0002, tarefas/0002,
   emails/0002, automacoes/0002) — `criado_em`/`criada_em`/`atualizada_em` → `created_at`/`updated_at`
   **preservando os dados existentes**; campos novos recebem backfill com o momento da migração
   (contatos antigos ganham `created_at` = data da migração — tradeoff anotado).
3. ✅ **Referências atualizadas** — views (acesso, dashboard, contatos, automacoes, tarefas) e
   templates (config, equipe, ficha, lista de automações) passaram a usar os novos nomes; a API já
   usava `created_at`/`updated_at`. Zero referências órfãs a `criado_em`/`criada_em`/`atualizada_em`
   fora de migrações.
4. ✅ **298 testes passando** (+7 novos em `teste/test_fase_k_timestamps.py`: conformidade de todos
   os modelos, renames preservaram dados, ordenações e telas seguem exibindo as datas).

### Fase L — S1 do PRD HAZON: rotulagem "Empresa" ✅ CONCLUÍDA (08/08/2026)

Executado por solicitação do cliente (S1 do PRD HAZON — renomear a rotulagem para "Empresa",
após os timestamps já padronizados na Fase K):
1. ✅ **Rótulos visíveis "Clínica" → "Empresa"** — mensagens de erro/sucesso do time
   (acesso/views.py: papel, dono, convite, membro), opções de papel "Admin da clínica" →
   "Admin da empresa" (config, equipe, convidar), textos de configuração (meta mensal,
   equipe, transferência de propriedade), kanban (modo leitura), dashboard (meta),
   automações (vazio/permissão) e formulário de contato.
2. ✅ **Extras de rebrand** — descrição da API no Swagger ("CRM da empresa"), PDF do orçamento
   (fallback sem tenant agora "HAZON CRM" e "Assinatura da empresa") e seed de demonstração
   ("Empresa Aurora (demonstração)").
3. ✅ **Preservados intencionalmente** — aliases de CSV do importador (`clinica`), slugs,
   comentários/docstrings internos, dados de teste e o rótulo de **segmento** "Clínica geral"
   (dado do nicho saúde, não rótulo de tenant — revisitar no rebrand de segmentos).
4. ✅ **298 testes passando** (77 re-rodados nas telas afetadas; `manage.py check` limpo).

### Fase M — S2 do PRD HAZON: design system centralizado ✅ CONCLUÍDA (08/08/2026)

Executado por solicitação do cliente (S2 do PRD HAZON — §9: tokens de cor/tipografia + componentes base):
1. ✅ **Tokens no Tailwind** (`theme/static_src/tailwind.config.js`) — paleta `hazon` completa
   (night/abyss/deep/surface/mid/primary/primary-dark/accent/text/muted/dim/success/warn/
   danger/info/orange/blue/slate/pink) substituindo a antiga `esfera` (que nunca foi usada nos
   templates — todos usavam hex hardcoded) + tokens de `boxShadow`; fontes Manrope + Fraunces.
2. ✅ **CSS variables e componentes** (`theme/static_src/src/styles.css`) — `:root` com as vars
   (inclusive `--hazon-form-input-border`/`--hazon-form-input-bg` alinhados ao visual original:
   borda `rgba(255,255,255,0.12)` e fundo `rgba(255,255,255,0.06)`) e biblioteca `@layer
   components`: `hazon-card`/`card-lg`/`card-sm`, `hazon-titulo`/`hazon-sub`, `hazon-label`,
   `hazon-btn`/`btn-primary`/`btn-ghost`, `form.hazon-form` (inputs/selects/textareas), `hazon-search`,
   `hazon-chip`, `tag-chip`, `hazon-th`/`hazon-td`.
3. ✅ **Migração byte-exact de 28 templates** (cards `rounded-2xl border-white/10 bg-white/5` →
   `hazon-card`/`card-lg`/`card-sm` preservando `backdrop-blur`; labels; botões primários/ghost;
   busca do kanban; títulos/subtítulos; chips; tag-check) — visual idêntico, zero mudança de valor.
4. ✅ **Centralização dos inputs** — os forms padrão (formulario, negocio_form, campos,
   editar_campo, equipe, config) ganharam `hazon-form` e os **blocos `<style>` duplicados de
   inputs foram removidos** (emails e ficha mantiveram estilos custom preservados); no config,
   os forms de ações (tema, excluir, sessão, transferir dono, cancelar convite) ficam sem a
   classe de propósito — só têm inputs hidden + botões.
5. ✅ **Rebuild do CSS** — componentes só entram no bundle quando usados (JIT tree-shake);
   rebuild após a migração; classes de componente presentes no `styles.css` compilado (40 KB).
6. ✅ **298 testes passando** + `manage.py check` limpo; revisão aplicada (paridade de borda/fundo
   dos forms, título 28px do formulario preservado via utility, cobertura 1:1 dos forms).

### Fase N — S3 do PRD HAZON: gestão de bases (carteiras + cargo) ✅ CONCLUÍDA (08/08/2026)

Executado por solicitação do cliente (S3 do PRD HAZON — Sprint 3, Gestão de bases):
1. ✅ **Modelo `Carteira`** (contatos/models.py + migração `0011`) — nome, descrição,
   `created_at`/`updated_at` e **nome único por tenant**; exclusão usa `SET_NULL`
   (contatos continuam existindo, só deixam de pertencer à carteira).
2. ✅ **Cargo no contato (3.2.7)** — campo `Contato.cargo` exibido no formulário, na
   ficha e na lista (sob a empresa); importável por CSV.
3. ✅ **Cliente associado à carteira (3.2.2)** — FK `Contato.carteira` (nullable),
   seletor no formulário escopado por tenant, filtro na lista de contatos e link na ficha.
4. ✅ **Telas de carteiras** — `/contatos/carteiras/` (listagem com contadores de
   contatos e fechados + criação só por admin) e `/contatos/carteiras/<id>/`
   (detalhe com resumo/filtro por etapa, editar e excluir só por admin);
   nav "📁 Carteiras" no header (com destaque correto — Contatos não fica ativo
   nas páginas de carteira via `match_urls`/`excluir_urls`).
5. ✅ **CSV associado à carteira (3.3.5)** — seletor "Carteira de destino" na
   importação + coluna Cargo mapeável; ids de carteira de outro tenant são descartados.
6. ✅ **API** — `GET/POST/DELETE /api/v1/carteiras` (isoladas por tenant; viewer não
   cria; nome só com espaços → 422) e `cargo`/`carteira_id` no payload/saída de
   contatos, com `CarteiraInvalida` → 400.
7. ✅ **328 testes passando** (278 web + 50 API, +31 novos na Fase N); `manage.py
   check` limpo; CSS rebuildado (classes dos novos templates no bundle).

### Fase O — S4 do PRD HAZON: e-mail avançado (cliques + conversão) ✅ CONCLUÍDA (08/08/2026)

Executado por solicitação do cliente (S4 do PRD HAZON — Sprint 4, bloco de e-mail
4.3: rastreio de cliques 4.3.5 e conversão de propostas 4.3.6):
1. ✅ **Rastreio de cliques** — `EmailEnviado` ganhou `cliques`, `ultimo_clique_em`
   e `convertido_em` (migração `emails/0003`); os links `href` http(s) do corpo do
   e-mail são reescritos para `/emails/clique/<token>/<código-b64url>/` (endpoint
   público que registra o clique — sempre atualizando o último — e redireciona,
   validando http/https contra `javascript:` e devolvendo 404 para token/código
   inválidos). Só `href` é rastreado (imagens não contam como clique — o pixel já
   mede abertura); links relativos e `mailto:` ficam intactos; sem reescrita dupla.
2. ✅ **Conversão de propostas (4.3.6)** — quando um negócio do contato fecha, os
   e-mails pendentes do contato ganham `convertido_em`. Hooks em **todos** os
   pontos de fechamento: funil (kanban mover), formulário do contato (editar),
   formulário do negócio (novo/editar) e API (criar, atualizar, mover etapa).
3. ✅ **UI de métricas** — a lista de e-mail (`/emails/`) ganhou KPIs (enviados,
   abertos %, cliques %, convertidos % com barras de progresso) e tabela
   "Últimos envios" (contato, modelo, status, aberto, cliques, conversão) com
   `select_related` (sem N+1).
4. ✅ **350 testes passando** (329 + 21 novos da Fase O); `manage.py check` limpo;
   revisão aplicada (ultimo clique em cada clique, regex só `https?://` e só href,
   hook do importador removido por ser inalcançável — dedup pula existentes e
   `pular_duplicadas=False` cria contato novo sem e-mails).

### Fase Q — S5 do PRD HAZON: Nation Dialer (fila + softphone + script) ✅ CONCLUÍDA (08/08/2026)

Executado por solicitação do cliente (S5 do PRD HAZON — Sprint 5, Nation Dialer;
o WhatsApp do S4 fica registrado como pendente de decisão de provedor):
1. ✅ **Fila (5.1)** — novo app `discador/` com modelo `Fila` (nome, descrição,
   carteira de origem, **ordem**: score / mais antigos / mais recentes, ativa,
   timestamps; migração `discador/0001`). Os contatos vêm da carteira (ou todos
   com telefone) e **a tela do operador (`/discador/`) exibe nome, empresa, cargo,
   telefone e score** (5.1.4) com a ordem configurada preservada.
2. ✅ **Softphone (5.2)** — camada `discador/softphone.py`: `uri_chamada` monta
   `sip:+<numero>@<dominio>` (MicroSIP e afins) ou `tel:+<numero>` conforme a
   configuração da empresa (`Tenant.softphone_schema`/`softphone_dominio`,
   migração `acesso/0010`, editável em Configurações → Discador). Ação única de
   chamada (5.2.2): o botão 📞 registra a `Chamada` (status `discada`, operador,
   timestamps) e abre a URI no softphone; o resultado é registrado em seguida
   (5.2.5) — realizada, ocupado, não atendeu, retornar (com data), sem interesse,
   acordo, erro — com observação.
3. ✅ **Script (5.3)** — modelo `Script` (roteiro por linhas, ativo) + CRUD em
   `/discador/scripts/`; cada fila referencia o próprio script, exibido **ao lado
   da fila na tela do operador durante a chamada** (5.3.3).
4. ✅ **RBAC e isolamento** — CRUD de filas/scripts só admin; iniciar/registrar
   chamada exige papel de edição (viewer bloqueado na web e 403 na API); filas,
   contatos e chamadas de outro tenant → 404.
5. ✅ **API** — `/api/v1/discador`: GET/POST `filas`, GET `filas/{id}/contatos`
   (com URI pronta), POST `filas/{id}/chamar` (201 + URI), POST
   `chamadas/{id}/resultado` e GET `scripts`.
6. ✅ **412 testes passando** (374 + 38 novos da Fase Q); `manage.py check` limpo;
   CSS rebuildado; revisão aplicada (ordem preservada na tela, N+1 eliminado com
   `prefetch_related('negocios')`/`select_related`, `int()` validado contra 500,
   CSRF confirmado pelo token global do header).

### Fase P — S4 do PRD HAZON: estrutura de campanhas (PRD 4.1) ✅ CONCLUÍDA (08/08/2026)

Executado por solicitação do cliente (S4 do PRD HAZON — Sprint 4, bloco 4.1:
estrutura de campanhas por canal, integrado ao e-mail já existente):
1. ✅ **Novo app `campanhas/`** — modelo `Campanha` (migração `0001`): nome, descrição,
   **canal** (email/whatsapp/telefone), `ativa` e timestamps, tudo escopado por tenant.
2. ✅ **`EmailEnviado` ganhou FK `campanha`** (nullable, SET_NULL — migração `emails/0004`)
   e `disparar_campanha()` agora aceita `campanha` e vincula os envios à campanha.
3. ✅ **Telas em `/campanhas/`** — lista (cards com canal, status e contadores de
   envios/convertidos), novo/editar/excluir (admin) e **detalhe** com KPIs reais
   (envios, abertos %, cliques %, convertidos %) + **disparo integrado**: escolhe
   modelo + segmento + carteira de destino, pré-visualiza o público e dispara
   (bloqueado se a campanha estiver inativa ou o canal não for e-mail).
   Nav "📣 Campanhas" no header (após E-mail).
4. ✅ **API** — `GET/POST /api/v1/campanhas` (isoladas por tenant; viewer → 403;
   canal inválido → 422; nome duplicado no tenant → 409).
5. ✅ **374 testes passando** (350 + 24 novos da Fase P); `manage.py check` limpo;
   CSS rebuildado (classes dos novos templates no bundle); revisão aplicada
   (sem N+1 — `prefetch_related('envios')`, permissões consistentes, `_base_pixel`
   duplicado na revisão apenas como observação menor).

### Fase R — S6 do PRD HAZON: acordos, follow-up e PIX ✅ CONCLUÍDA (08/08/2026)

Executado por solicitação do cliente (S6 do PRD HAZON — Sprint 6, CRM, follow-up e
acordos; o funil/CRM já existia — completamos follow-up automático, simulador
financeiro e PIX):
1. ✅ **Novo app `acordos/`** — modelos `RegraDesconto` (desconto por modalidade +
nº de parcelas, configurável por empresa) e `Acordo` (valor original, modalidade,
parcelas, % e R$ de desconto, valor final, status proposta→aceito→pix_gerado→
enviado→pago→recusado, `pix_payload`, `pago_em`; migração `acordos/0001`).
2. ✅ **Simulador financeiro (6.3)** — `acordos/servico.py` aplica as regras do
tenant (fallback padrão da casa: vista 30%, parcelado 2x 20% / 3x 15% / 6x 8%) com
desconto progressivo, valor final e parcela mensal (resto de centavo na última);
formulário em `/acordos/simular/` e por contato; registro do acordo aceito (6.3.8).
3. ✅ **PIX / BR Code estático (6.4)** — `acordos/pix.py` implementa o payload EMV
copia-e-cola (TLV + CRC16-CCITT, `_crc16`/`montar_payload_pix`) e QR Code em SVG
(lib `qrcode`) — **sem provedor externo** (decisão do cliente no S6). O detalhe do
acordo gera o PIX sob demanda (`?gerar_pix=1`), mostra copia-e-cola + QR, link
`wa.me` p/ envio pelo WhatsApp (6.4.7) e ações marcar pago / recusar (6.4.8).
4. ✅ **Follow-up automático (6.2)** — resultado de chamada **"Retornar depois"**
no discador cria `Tarefa` (título "Retornar ligação", vencimento = `retorno_em`,
prioridade alta, contato e responsável preenchidos) — integração S5 → S6.
5. ✅ **Config por empresa** — seção em `/config/` para dados do PIX (chave,
recebedor, cidade — `Tenant.pix_*`, migração `acesso/0011`) e regras de desconto
(admin); operacional não vê.
6. ✅ **API** — `POST /api/v1/acordos/simular`, `POST /api/v1/acordos` e
`POST /api/v1/acordos/{id}/resultado`: contato de outro tenant → 404, viewer → 403.7. ✅ **438 testes passando** (412 + 26 novos da Fase R); `manage.py check` limpo;
   CSS rebuildado; revisão aplicada (payload EMV válido com CRC conferindo, valores
   Decimal sem float, isolamento entre tenants, RBAC web + API).

### Fase S — S7 do PRD HAZON: dashboard e relatórios gerenciais ✅ CONCLUÍDA (08/08/2026)

Executado por solicitação do cliente (S7 do PRD HAZON — Sprint 7, seção 7: dashboard
de cobrança com KPIs, filtros de período e exportação PDF/CSV):
1. ✅ **Novo app `relatorios/`** (sem modelos — lê dos apps existentes) com página em
   `/relatorios/`: KPIs de cobrança **base** (contatos com telefone válido + badge de
   novos no período), **CPC** (chamadas com resultado `realizada`), **retornos**
   (agendados p/ o período via `retorno_em`), **acordos** (criados, exceto recusados,
   com badge de pagos), **valor recuperado** (acordos pagos no período) e
   **produtividade** (chamadas iniciadas). Nav "📊 Relatórios" no header (após Campanhas).
2. ✅ **Produtividade por operador (7.1.6)** — tabela com chamadas, realizadas,
   retornos, acordos e valor recuperado por operador (agregação por `chamada__operador`,
   sem N+1 — 3 queries agregadas).
3. ✅ **Filtros de período (7.2)** — Hoje / Últimos 7 dias / Últimos 30 dias (padrão) /
   Mês corrente via `?periodo=`; aplicado a todos os KPIs e à produtividade.
4. ✅ **Exportação (7.3)** — **CSV** com BOM UTF-8, separador `;`, proteção contra
   injeção de fórmula (`_csv_seguro`) e **PDF** via reportlab (cabeçalho da empresa,
   faixa do período, grade de KPIs e tabela de produtividade; fonts padrão Latin-1).
5. ✅ **Segurança** — escopo por tenant em todas as queries (`tenant_id` da sessão),
   `web_login_required` nas 3 rotas, arquivos com nome fixo (sem injeção); o filtro
   `?operador=` valida o id contra o tenant da sessão (id de outro tenant é ignorado).
6. ✅ **Gráficos da série diária (30 dias)** — SVG no mesmo visual do dashboard:
   linha multi-série "Atividade diária" (CPC × acordos) e "Valor recuperado por dia",
   com área suave, pontos com tooltip e legenda; barras de valor recuperado por
   operador na seção de produtividade.
7. ✅ **Filtro por operador** — select "Operador" (admin/operacional do tenant) no topo
   da página; restringe CPC/retornos/acordos/valor/produtividade (a base continua da
   empresa inteira); preservado nos links de período e na exportação CSV/PDF.
8. ✅ **Comando `enviar_relatorio`** — gera o PDF por empresa e envia por e-mail aos
   admins (`--tenant` opcional, `--periodo` hoje/7/30/mes); sem SMTP roda em modo
   simulação (loga o que enviaria). Agendável (Task Scheduler/cron).
9. ✅ **452 testes passando** (438 + 14 novos da Fase S, incl. série diária/gráficos,
   filtro por operador e o comando `enviar_relatorio` em modo simulação e SMTP);
   suíte relacionada verde (dashboard, discador, acordos, timestamps = 83/83);
   `manage.py check` limpo; sem migrações pendentes; CSS rebuildado (classes do
   novo template).

### Fase T — S8 do PRD HAZON: revisão de interface e segurança ✅ CONCLUÍDA (08/08/2026)

Auditoria completa de interface e segurança, com correções aplicadas (S8 do PRD
HAZON — Sprint 8: 8.1 design system, 8.2 conteúdo, 8.3 segurança):
1. ✅ **Bug de autenticação corrigido (8.3.1)** — `campos_personalizados`,
   `editar_campo` e `excluir_campo` exigiam apenas `@web_requer_admin` (qualquer
   pessoa não logada acessava `/contatos/campos/`). Adicionado `@web_login_required`
   (padrão do projeto: login + admin em todas as rotas de gestão).
2. ✅ **Design system (8.1)** — novo componente **`hazon-btn-danger`** no
   `theme/static_src/src/styles.css` (vermelho translúcido com hover, mesmo padrão
   dos demais); todos os **botões primários antigos** (gradiente manual
   `bg-gradient-to-br from-[#0b6f74] to-[#075b60]`) migrados para
   `hazon-btn hazon-btn-primary` e os botões de excluir/cancelar convite/encerrar
   sessão padronizados com `hazon-btn-danger` em ~20 templates (equipe, campos,
   importar, formulários, listas, discador, acordos, e-mails, campanhas, config,
   detalhes de contato). Páginas públicas standalone (login/onboarding/convite/captura)
   mantêm o visual hero próprio, intencional.
3. ✅ **Segurança (8.3)** — `ALLOWED_HOSTS` configurável por ambiente
   (`DJANGO_ALLOWED_HOSTS` no .env, anti host-header spoofing; dev sem variável
   continua `*`, mas em produção **falha fechado** — sem a variável, só aceita
   localhost, evitando abrir mão silenciosamente da proteção); listagem de sessões
   ativas (`acesso/views.py` `_sessoes_do_usuario`) agora filtra sessões já expiradas
   no banco antes de decodificar (menos volume e dados obsoletos).
4. ✅ **Conteúdo (8.2)** — varredura PT-BR de todas as telas (textos, acentos,
   cedilha, til): limpa; os únicos matches eram placeholders de template intencionais.
5. ✅ **Auditoria de autorização/isolamento/endpoints (8.3.2/8.3.3/8.3.6)** —
   decorators confirmados em todas as views web, `filtro_tenant` nas queries,
   rotas públicas intencionais (login/onboarding/captura/rastreio) verificadas.
6. ✅ **463 testes passando** (452 + 11 novos da Fase T/S8: campos exigem login
   (anônimo/admin/operacional), botões padronizados renderizam `hazon-btn-primary`/
   `hazon-btn-danger`, ALLOWED_HOSTS configurável com parsing/fail-closed e filtro
   de sessões expiradas);   `manage.py check` limpo; sem migrações pendentes; CSS
   rebuildado (novas classes `hazon-btn-danger` no bundle).

### Fase U — S9 do PRD HAZON: documentação técnica ✅ CONCLUÍDA (08/08/2026)

Documentação criada em `DOCS/` descrevendo **somente o que existe** no projeto
(Sprint 9 do PRD HAZON — seção 9.1, pasta DOCS):
1. ✅ **`DOCS/README.md`** — índice da documentação com referência rápida
   (portas, testes, Tailwind).
2. ✅ **`DOCS/architecture.md`** — camadas (Django DTL + FastAPI + legado Node),
   apps, fluxos de requisição web/API e multi-tenancy.
3. ✅ **`DOCS/backend.md`** — todos os apps e modelos (acesso, contatos,
   agendamentos, funil, emails, tarefas, automacoes, campanhas, discador,
   acordos, relatorios), decorators, comandos de gerenciamento e serviços.
4. ✅ **`DOCS/frontend.md`** — templates DTL, base/nav, mapa de telas, SVG
   gerados em Python e interações JS por página.
5. ✅ **`DOCS/database.md`** — configuração PostgreSQL, tabelas por app com
   campos-chave, multi-tenancy por coluna e índices relevantes.
6. ✅ **`DOCS/security.md`** — autenticação (sessão/JWT), RBAC, isolamento por
   tenant, headers/CSP, ALLOWED_HOSTS (S8), segredos e rotas públicas.
7. ✅ **`DOCS/design-system.md`** — tokens CSS e componentes `hazon-*` com
   regras de uso.
8. ✅ **`DOCS/api.md`** — autenticação JWT, rotas por módulo e padrões
   route→service→repository da API `/api/v1`.
9. ✅ **`DOCS/development-guidelines.md`** — convenções de código, multi-tenancy,
   segurança, frontend, banco, testes e comandos úteis.
10. ✅ Regra 9.1.11 respeitada: nada inexistente foi documentado — cada arquivo
    foi escrito a partir da leitura do código real (models, urls, views,
    settings, middleware, styles.css).

### Próxima rodada — lista ordenada (a construir, decisão do cliente)
1. ~~**Lead scoring simples**~~ ✅ (Fase J).
2. ~~**Orçamento/proposta em PDF**~~ ✅ (Fase J).
3. ~~**Metas por vendedor**~~ ✅ (Fase J).
4. **Chat web ao vivo** — widget no site (sem WhatsApp).
5. **Webhooks outbound / integrações** — exportar eventos pra outros sistemas.
6. **Catálogo de serviços** — produtos/serviços com preço (base pra orçamento).
7. **IA** — resumo de notas, sugestão de próximo passo, escrita de e-mail.
8. **Mobile nativo** — app iOS/Android (hoje o web é responsivo).

---

## 9. Próximas decisões (para conversarmos)

1. ~~Qual fase priorizar?~~ → Executadas: A, A1, B (time/config), viewer, C1 (dashboard), D (qualidade/segurança).
2. **WhatsApp (Fase C): provedor?** Meta Cloud API oficial × Evolution API (self-hosted) × BSP (360dialog/Z-API) — planejado, decisão adiada.
3. O nicho principal continua sendo **saúde/estética**?
4. ~~Deals separados ou manter `stage + valor` no contato?~~ → resolvido: entidade `Negocio` 1:N.
5. Manter PT-BR apenas (recomendado) ou partir pra i18n?
6. **Transferência de dono** ✅ concluída (GAP #9 fechado — time completo).
7. Teste visual no navegador: agente browser-use com runtime instável nesta máquina — usar verificação programática (client) como fallback enquanto isso.
8. **Pipeline configurável por tenant** ✅ concluída (Fase F — item 2 da rodada; etapas/cores/pesos próprios por clínica, gestão em `/config/#etapas`, guardas de exclusão, API validando etapa).
9. **Tarefas & lembretes** ✅ concluída (Fase G — item 1 da rodada; `/tarefas/` com seções atrasadas/hoje/próximas, badge no header, alerta no dashboard, follow-ups na ficha do contato).
10. **Formulário público de captura de lead** ✅ concluído (Fase H — item 1 da rodada; link `/captura/<token>/` sem login → contato + negócio na 1ª etapa, honeypot, rate limit por IP, dedup por telefone, origem configurável em `/config/#captura`).
11. **Lead scoring + orçamento em PDF + metas por vendedor** ✅ concluídos (Fase J — itens 1–3 da rodada; score 🔥 em ficha/lista/kanban com ordenação por prioridade, orçamento reportlab por negócio, metas por vendedor em `/config/#metas-vendedores` + dashboard).
12. Próximos da fila: **chat web ao vivo**, **webhooks outbound**, **catálogo de serviços**, **IA**, **mobile nativo** (ver §8).
13. **Timestamps padronizados** ✅ concluído (Fase K — §7.6 do PRD HAZON: `created_at`/`updated_at` em todos os 22 modelos, renames preservando dados, 298 testes).
14. **S1 do PRD HAZON (rotulagem "Empresa")** ✅ concluído (Fase L — rótulos visíveis Clínica → Empresa + marca HAZON CRM; timestamps já na Fase K).
15. **S2 do PRD HAZON (design system centralizado)** ✅ concluído (Fase M — tokens `hazon` no Tailwind + CSS vars + componentes `hazon-*` + migração de 28 templates com visual idêntico; próxima: S3 — carteiras + cargo no contato).
16. **S3 do PRD HAZON (gestão de bases)** ✅ concluído (Fase N — modelo Carteira por tenant + cargo no contato + telas de listagem/detalhe + filtro + CSV com carteira + API; 328 testes).
17. **S4 do PRD HAZON (e-mail avançado)** ✅ concluído (Fase O — rastreio de cliques com endpoint público + conversão de propostas quando o negócio fecha + KPIs/histórico na lista de e-mail; 350 testes).
18. **S4 do PRD HAZON (estrutura de campanhas)** ✅ concluído (Fase P — app `campanhas` com modelo por canal, telas de lista/detalhe, disparo de e-mail integrado com KPIs e API; 374 testes). Resta do S4: **WhatsApp (4.2)** — aguarda decisão de provedor (Meta × Evolution × BSP).
19. **S5 do PRD HAZON (Nation Dialer)** ✅ concluído (Fase Q — filas com ordenação + tela do operador com nome/empresa/cargo/telefone/score, ação única de chamada via URI sip:/tel: com MicroSIP, registro de resultado da chamada, scripts de atendimento exibidos durante a chamada, configuração do softphone por empresa e API; 412 testes). **S6 — CRM, follow-up e acordos** ✅ concluído (Fase R — simulador financeiro, acordos com status, PIX BR Code + QR, follow-up automático do discador, config por empresa e API; 438 testes). **S7 — Dashboard e relatórios** ✅ concluído (Fase S — relatório gerencial com base, CPC, retornos, acordos, valor recuperado e produtividade por operador, filtros hoje/7d/30d/mês, gráficos da série diária, filtro por operador, comando `enviar_relatorio` e exportação CSV+PDF; 452 testes). **S8 — Revisão de interface e segurança** ✅ concluído (Fase T — bug de autenticação nos campos personalizados corrigido, botões padronizados com `hazon-btn-danger`, ALLOWED_HOSTS configurável com fail-closed em produção, sessões expiradas filtradas; 463 testes). **S9 — Documentação** ✅ concluído (Fase U — 9 documentos em `DOCS/` descrevendo apenas o que existe: README, architecture, backend, frontend, database, security, design-system, api e development-guidelines).
