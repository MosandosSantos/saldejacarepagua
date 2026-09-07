# Sprint Plan — Port do "Sal do RER" para Django

| | |
|---|---|
| **Base** | `DOCS/PRD-DJANGO.md` (requisitos, modelos, matriz de permissões) |
| **Formato** | 1 sprint de preparação + 12 sprints de 2 semanas (≈ 6 meses) |
| **Equipe de referência** | 1–2 devs full-stack |
| **DoD global** | Código revisado · testes pytest passando · paridade com o legado verificada por checklist do módulo · migrações rodando de `zero` e sobre cópia real do banco |

---

## Convenções

- **Nomenclatura**: novos campos já nascem com **Recepção** (`recepcao_mx`, `recepcao_ec`) — nunca usar "apresentação" no Django (ver PRD §5).
- **Toda tarefa** segue o ciclo: model+migration → service/queryset → view(s) → template → testes → checklist de paridade.
- **Testes**: `pytest-django`; factories em `core/factories.py`; fixtures de papéis reutilizáveis.
- **Checklist de paridade**: cada sprint lista as telas/endpoints do legado que devem existir e se comportar igual.

---

## Sprint 0 — Preparação (1 semana)

**Objetivo**: ambiente, decisões e esqueleto prontos.

1. Repo `saldarer-django` (monorepo ou novo), CI (GitHub Actions: lint `ruff` + `pytest` + migrações em Postgres de serviço).
2. Projeto Django 5: `config/settings/{base,dev,prod}.py`, `.env` (DATABASE_URL, R2, SMTP, SECRET), `TIME_ZONE="America/Sao_Paulo"`, `USE_TZ=True`.
3. Tailwind standalone + tema dark (tokens `obs-*` do `globals.css` legado), fontes Geist/Cinzel, Alpine.js e Chart.js em `static/`.
4. Apps vazios conforme PRD §4.1; `core` com: `TenantMiddleware` (resolve tenant do user), `AuditLog`, managers `TenantQuerySet.for_user(user)`, `core/roles.py` (funções da matriz PRD §6.2), `core/phone.py` (normalização de celular BR), exceções tipadas.
5. `PASSWORD_HASHERS` com BCrypt primeiro; testar decode de hash real do legado.
6. docker-compose (Postgres 16 + web) e README.

**Entrega**: `/health` respondendo; shell do Django criando Tenant/User com senha bcrypt legada.

---

## Sprint 1 — Autenticação, contas e onboarding

**Objetivo**: paridade total de `accounts` (PRD §8.1).

1. **Modelos**: `User`, `AuthAttempt`, `PasswordInviteToken` (+ migrações). Soft delete `deleted_at`.
2. **Login por celular + senha**: form com máscara; rate limit (cache) + `AuthAttempt` (lock); só `status=ACTIVE` e loja ATIVA; `AuditLog` LOGIN; `last_login_at`.
3. **Middleware de guarda** (equiv. AuthEnforcer): não autenticado → `/login?next=`; `must_change_password` → `/senha` (forçada); `must_complete_profile` → `/primeiro-acesso/completar-cadastro`.
4. **Sessão**: login/logout; troca de senha com política forte; re-autenticação `verify-password` (view POST usada por ações sensíveis).
5. **Convite**: criar token (SHA-256, 48h, código 6 dígitos, 5 tentativas) → e-mail template 1; `/auth/set-password` valida código → define senha → `ACTIVE`.
6. **Esqueci a senha**: exige e-mail + celular; rate 3/15min; resposta genérica; template 2.
7. **Primeiro acesso do membro**: página completa de perfil (seções identificação/documentos/endereço/escolaridade), destaca faltantes, salva e limpa `must_complete_profile`.
8. **Testes**: login válido/inválido/lock; fluxo convite completo; forgot-password; guardas de middleware; bcrypt legado.

**Paridade**: `/login`, `/auth/set-password`, `/auth/forgot-password`, `/senha`, `/primeiro-acesso/completar-cadastro`, `/logout`.

---

## Sprint 2 — Organizacional (Prefeituras, Lojas, catálogos)

1. **Modelos**: `Prefeitura`, `Loja`, `Potencia`, `Rito`, `Class` (+ seeds dos catálogos e classes MX/EC/CBCS/SC).
2. **Managers com escopo**: global (SaaS), prefeitura (PREFEITO), tenant.
3. **Prefeituras**: listagem com contagens (lojas/membros), detalhe (404 para restritos fora do escopo), CRUD com views POST (equiv. Server Actions); exclusão bloqueada com lojas vinculadas.
4. **Lojas**: listagem com KPIs (total/ativas/membros), CRUD completo — validação de CNPJ, `short_name` único (checa `Tenant.name`), prefixo "Grande Priorado -"/"GP-" no GPRB, dados bancários, mensalidades regular/remida, sincronização `Tenant.name`; exclusão bloqueada com vínculos (members/users/payments/dues/meetings).
5. Modal "membros da loja"; endpoint interno `lojas/{id}/valores` (fallbacks 500/150/150).
6. Sidebar + breadcrumbs + shell (colapsável, mobile sheet, topbar com tenant) e controle de itens por papel (`main-nav`).
7. **Testes**: escopos por papel; unique short_name; bloqueios de exclusão.

**Paridade**: `/potencias*`, `/admin/lojas*`, menu lateral com visibilidade correta.

---

## Sprint 3 — Membros (cadastro, ficha, datas de Recepção)

1. **Model** `Member` completo (PRD §7.3) com `recepcao_mx` / `recepcao_ec` / `armadura_cbcs`; migração de renomeação preparada (roda sobre cópia real no Sprint 12).
2. **Validações**: datas cronológicas (Recepção MX obrigatória na criação; EN ≥ MX; CBCS ≥ EN); CPF unique/tenant; celular normalizado; classe mínima MX.
3. **Listagem** `/membros`: KPIs, busca, filtros situação/classe/loja, paginação, badges de grau; ações por papel (ver/editar/histórico/datas/excluir).
4. **CRUD**: novo (form completo + selects de lojas/classes/prefeituras), detalhe em seções, editar, excluir **transacional** (zera inventário, apaga PaymentStatus/Payment/DuesCharge/MemberPayment+Lancamento/Attendance/User vinculado).
5. **Datas cavaleirescas**: página de edição (Recepção MX/EN + Armadura + lojas correspondentes).
6. `ensure_member_user` (cria User MEMBER vinculado por celular/e-mail); envio de convite ao membro.
7. **Testes**: validações de data; exclusão em cascata; escopos (Delegado/Secretário só própria loja; Tesoureiro read-only).

**Paridade**: `/membros*` (6 rotas).

---

## Sprint 4 — Financeiro (contas, categorias, dashboard financeiro)

1. **Modelos**: `Categoria`, `Lancamento` (+ unique categoria por tenant/nome/tipo).
2. **Contas**: listagem com filtros tipo/status/período, CRUD com validação categoria↔tipo, status ABERTO/PARCIAL/PAGO/ATRASADO/PREVISTO; exclusão.
3. **Categorias**: CRUD com bloqueio de exclusão em uso.
4. **Dashboard financeiro**: KPIs (a pagar/receber, pago/recebido, saldos), comparativos ano/mês, gráfico de fluxo mensal realizado + previsto (Chart.js), **Previsão de Caixa** com linhas expansíveis, pizza por categoria.
5. **Testes**: gating `can_view_finance` (Grande Prior bloqueado!) vs `can_manage_finance`; cálculos dos agregados com fixtures.

**Paridade**: `/financeiro*` (5 rotas), `/api/contas*` (dados vindos das views Django).

---

## Sprint 5 — Pagamentos de membros (grade mensalidade/anuidade/iniciações)

1. **Modelos**: `PaymentPeriod`, `PaymentStatus`, `MemberPayment`, `PaymentAuditLog`; gerador de períodos (12 meses/anual) via management command `generate_periods`.
2. **Grade** `/pagamentos`: 3 abas (Mensalidade/Anuidade/Iniciações), matriz membro × período com totais e linha "TOTAL DO ANO"; filtros ano/loja; KPIs por aba; mobile cards.
3. **Marcar pagamento** (modal): PENDING/PAID/CANCELED + amount/method/paid_at/notes → grava status + **PaymentAuditLog**; regras: `can_mutate_payments` (Grande Chanceler bloqueado), aba mensalidade restrita (§6.2), REMIDO fora da grade mensal, MEMBER vê só a própria linha.
4. **Registrar pagamento**: cria `Lancamento` RECEITA PAGO + `MemberPayment` (categoria auto "Mensalidades"/"Anuidades").
5. **Histórico**: `/membros/{id}/pagamentos` (KPIs + registro) e `/pagamentos/historico/{id}`; bloqueio `can_view_member_payment_pages` (Grande Chanceler/Prefeito).
6. **Billing legado**: `Payment`/`DuesCharge`/`KpiSnapshot` + summary e matriz (mantidos para paridade de dados).
7. **Testes**: mark/register; auditoria; gating completo; duplicidade.

**Paridade**: `/pagamentos`, `/pagamentos/historico/[id]`, `/financeiro/pagamentos`.

---

## Sprint 6 — Presença e Ranking

1. **Modelos**: `Meeting`, `Attendance` (unique meeting+member).
2. **Sessões**: listagem com KPIs anuais e filtros; CRUD (6 tipos); exclusão bloqueada com presenças; escopo de loja (fixo para MEMBER/Secretário/Tesoureiro/Delegado).
3. **Marcação** `/presenca/{id}`: grid membro × classe × status (PRESENTE/FALTA/JUSTIFICADA) com upsert em lote; **bloqueio de sessões futuras** (`SESSION_NOT_HAPPENED_YET`, TZ SP); edição só ADMIN_LOJA/SECRETARIO_LOJA; leitura com badges para os demais.
4. **Frequência** (componente compartilhado): % por membro, janelas 18 meses (MX) e 12 meses (EC), com colunas **"Recepção (MX)" / "Recepção (EC)"** e ordenação por tempo de **recepção**.
5. **Ranking** `/ranking`: seleção MX/EC, janela 24 meses, KPIs, filtro loja.
6. **Relatórios** `/presenca/relatorios`: por período e por membro, com layout de impressão.
7. **Testes**: fuso horário nas fronteiras; upsert; gating `can_mark_or_delete_presence_at_loja` (Tesoureiro não marca).

**Paridade**: `/presenca*` (4 rotas), `/ranking`, `/presencas` (redirect).

---

## Sprint 7 — Candidatos (admin + workflow de 7 níveis)

1. **Modelos**: `Candidato`, `CandidatoObservacao` (PRD §7.4).
2. **Workflow** `candidatos/workflow.py`: níveis `DM→PREFEITO→TESOUREIRO→CHANCELER→PRIOR→CHANCELER_2→DM_FINAL`, mapa papel→nível, bypass SYS_ADMIN, `pode_aprovar` (GRANDE_PRIOR/GRAO_MESTRE/SYS_ADMIN). **Service layer com transições atômicas**.
3. **Listagem** `/candidatos`: KPIs por status, filtros status/grau, ações condicionais por papel (enviar ficha, aprovar DM, encaminhar/devolver com observação, aprovar final, devolver ao candidato, iniciar, excluir).
4. **Ficha** `/candidatos/{id}`: trilha visual dos 7 níveis + dados + documentos com preview.
5. **CRUD + ações**: criar (EM_ANALISE), editar, excluir; `aprovar-dm`; `encaminhar`/`devolver` (±1 nível, observação opcional); `approve` (APROVADO + data); `devolver-candidato` (DEVOLVIDO_CANDIDATO).
6. **Iniciação**: transforma em Member (classe MX, INIC, cargo por grau) + User; valida CPF/nascimento/duplicidade; status INICIADO + `data_inicio`.
7. Observações (máx 5000) com autor/papel.
8. **Testes de integração**: caminho completo EM_ANALISE→INICIADO; tentativa de transição fora de ordem por papel errado (403); bypass.

**Paridade**: `/candidatos*` (4 rotas) — **coração do negócio, prioridade máxima de testes**.

---

## Sprint 8 — Portal do candidato (Súplica) + e-mails

1. **Acesso**: envio da ficha por e-mail (token 32 bytes→hash, 7 dias) → template 4 (link + **código de 4 dígitos** + checklist com "quitação da **recepção** ao grau pretendido"); `/candidato-acesso/{token}` → set-password (uso único + código, 5 tentativas) → role CANDIDATO.
2. **`/candidato/dashboard`**: card de status com datas e descrição; CTA "Terminar a Súplica".
3. **`/candidato/suplica`**: formulário completo (dados pessoais, endereço, loja simbólica com potências/ritos), **uploads de 3 documentos** (foto/quitação/comprovante para R2), salvar rascunho vs enviar (→ FICHA_ENVIADA), bloqueio de campos após envio, observações recebidas, tela de sucesso com texto da **cerimônia de recepção**.
4. Template 3 ("ficha enviada").
5. **Testes**: ciclo token/código completo; expiração; reenvio; uploads; bloqueios.

**Paridade**: `/candidato/*`, `/candidato-acesso/[token]`.

---

## Sprint 9 — Inventário

1. **Modelos**: `InventoryItem`, `InventoryMovement`.
2. **Serviço de movimentação** (transacional): IN recalcula custo médio; OUT valida saldo; ADJUST delta não-negativo; ARCHIVE registra; snapshot before/after (qty/avg_cost) + ip/user-agent.
3. **Listagem** `/inventario`: KPIs, filtros (busca, atribuído, abaixo do mínimo, arquivados), cards, export **CSV/PDF** (pdf-lib→`reportlab` ou `weasyprint`).
4. **Detalhe** com histórico + dialogs de movimentação; **arquivamento exige senha + motivo** (usa `verify-password`).
5. `/meu-material` (itens atribuídos ao membro logado); redirects `/inventario/novo` e `/inventario/logs`.
6. **Testes**: custo médio (casos com devolução/zeragem), saldo negativo, gating (MEMBER 403; movimentações ADMIN_LOJA/TESOUREIRO).

**Paridade**: `/inventario*` (5 rotas), `/meu-material`.

---

## Sprint 10 — Chancelaria

1. **Modelos**: `ChancelariaDocument`, `ChancelariaDocumentEvent`; geração de protocolo `{PREFIXO5}-{NUM4}-{AA}` (unique por tenant).
2. **Upload/download R2** (`django-storages`): chaves sanitizadas; download respeita visibilidade.
3. **Listagem** com abas SENT/RECEIVED, filtros (status/busca), visibilidade em camadas por papel (PUBLIC/LOJA/PREFEITOS/GPRB/CHANCELER); eventos registrados.
4. **Exclusão** só SYS_ADMIN/GRANDE_CHANCELER.
5. **Testes**: matriz papel × visibilidade; protocolo único; eventos.

**Paridade**: `/chancelaria`.

---

## Sprint 11 — Dashboard executivo + Usuários

1. **Dashboard `/`**: KPIs (lojas ativas, membros ativos, sessões do ano, caixa p/ Grão-Conselho); gráficos (grau com ordem AP→NI, potência, rito, idades+mediana, admissões 36m com fallback admissão→recepção_mx→criação, frequência 24m, caixa realizado/projetado, categorias); **mapa do Brasil** (proxy geocode Nominatim com cache 12h) e **calendário de sessões** interativo; ações rápidas com gating.
2. **Usuários**: listagem (filtros, paginação, último acesso via AuditLog); criação (senha temporária ou convite; opções de papel conforme ator; PREFEITO só própria prefeitura; roles SaaS exigem `can_assign_privileged_org_roles`; loja GPRB forçada); edição; exclusão (não a si mesmo); reenvio de convite.
3. **Testes**: agregações do dashboard com fixtures; matriz de criação de usuários.

**Paridade**: `/`, `/usuarios*`, `/quiz`, `/comunicacao`, `/biblioteca`, `/mensalidades` (placeholders).

---

## Sprint 12 — API externa, migração de dados e cutover

1. **API externa (DRF)**: endpoints `external/lojas`, `external/prefeituras`, `external/prefeituras/{id}/lojas`; auth por Service Token (prefix+SHA-256, scopes, revogação); CORS; rate limit 60/min global + 30/min token; `ExternalApiAuditLog`; OpenAPI (drf-spectacular) + Swagger UI.
2. **Health/ready** finais + logging estruturado.
3. **Migração de dados** (ensaio geral em staging):
   - restore do dump de produção;
   - migração Django (`migrate`) — inclui **RenameField** `apresentacao_mx→recepcao_mx`, `apresentacao_ec→recepcao_ec`;
   - validação de contagens por tabela × legado; conferência de totais financeiros; login com hash bcrypt real;
   - comandos `generate_periods` idempotentes.
4. **Cutover**: janela acordada; legado em modo leitura; restore final; smoke tests (login, ficha de membro, grade de pagamentos, protocolo chancelaria, súplica do candidato); rollback documentado.
5. **Testes**: contratos da API externa; auditoria de rate limit.

---

## Rastreabilidade rápida (paridade total)

| Módulo legado | Sprints |
|---|---|
| Auth/conta/primeiro acesso | 0, 1 |
| Prefeituras/Lojas/shell | 2 |
| Membros + Datas de Recepção | 3 |
| Financeiro | 4 |
| Pagamentos/Billing | 5 |
| Presença/Ranking/Relatórios | 6 |
| Candidatos (workflow) | 7 |
| Portal do candidato/Súplica/e-mails | 8 |
| Inventário | 9 |
| Chancelaria | 10 |
| Dashboard/Usuários/placeholders | 11 |
| API externa/dados/cutover | 12 |

**Critério de "pronto" do projeto**: todos os itens de §2.2 do PRD verdes + checklist de paridade por módulo assinado + cutover concluído com smoke tests.
