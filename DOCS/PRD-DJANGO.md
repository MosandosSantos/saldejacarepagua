# PRD — Port do Sistema "Sal do RER" para Django

| | |
|---|---|
| **Documento** | Product Requirements Document (PRD) |
| **Origem** | Sistema legado: Next.js 15 (App Router) + Prisma + PostgreSQL — `app/src` |
| **Destino** | Aplicação Django 5 (monólito full-stack) |
| **Data** | Setembro/2026 |
| **Status** | Versão 1.0 — base para o Sprint Plan (`DOCS/SPRINT-PLAN-DJANGO.md`) |
| **Nota de nomenclatura** | A partir desta versão, o termo **"Apresentação"** passa a se chamar **"Recepção"** (ver §5) |

---

## 1. Visão do Produto

O **Sal do RER** é o sistema de gestão da **Grande Priorado Retificado no Brasil (GPRB)** — organização maçônica retificada estruturada em **Prefeituras (Potências)** que administram **Lojas**, compostas por **Membros** (graus MX, EC, CBCS). O sistema centraliza:

1. **Cadastro ritualístico e administrativo de membros** (ficha completa, datas cavaleirescas, documentos);
2. **Fluxo de admissão de candidatos** (Súplica) com workflow de aprovação multinível (7 níveis);
3. **Presença em sessões** (6 tipos) com frequência, relatórios e **ranking ritualístico** (MX/EC, janela 24 meses);
4. **Financeiro** (contas a pagar/receber por categoria, fluxo de caixa realizado e projetado);
5. **Pagamentos de membros** (mensalidade da loja, anuidade do priorado, iniciações — grade membro × período);
6. **Inventário** com custo médio móvel, movimentações IN/OUT/ADJUST e arquivamento auditado;
7. **Chancelaria** (gestão documental com protocolo, visibilidade em camadas e storage em objeto);
8. **Estrutura organizacional** (Prefeituras, Lojas com dados bancários e mensalidades);
9. **Usuários e autenticação** com 12 papéis, escopos multi-tenant e convites por e-mail;
10. **Dashboard executivo** com KPIs, 8+ gráficos, mapa do Brasil e calendário de sessões;
11. **API externa** com Service Tokens (scopes, rate limit, auditoria, OpenAPI/Swagger).

### 1.1 Contexto multi-tenant
- Todo dado pertence a um `Tenant` (loja base **GPRB** = Grande Priorado).
- Usuários de nível "Grande" (6 papéis SaaS) têm visão global; `ADMIN_LOJA`/`SECRETARIO_LOJA`/`TESOUREIRO`/`MEMBER` são confinados à própria loja; `PREFEITO` à própria prefeitura.
- **Regra de ouro**: toda query é filtrada por `tenant_id` + escopo de papel. Isso deve ser garantido por **querysets/managers no Django** (não por filtros ad-hoc nas views).

---

## 2. Objetivos e Critérios de Sucesso

### 2.1 Objetivos
1. **Paridade funcional 1:1** com o sistema atual (60 rotas de página, ~59 endpoints, 30 modelos).
2. Adotar a nova nomenclatura ritualística (**Recepção** no lugar de Apresentação) desde o primeiro dia.
3. Simplificar hospedagem e operação (monólito Django, sem pipeline Node em produção).
4. Preservar os dados existentes via **migração de dados direta** (mesmas tabelas/colunas ou renomeação controlada).
5. Manter o design system (tema dark, identidade "obs-*", fontes Geist/Cinzel) em templates Django + Tailwind.

### 2.2 Critérios de aceite
- [ ] Todos os fluxos críticos (§9) funcionam ponta a ponta em ambiente de homologação com dados migrados.
- [ ] Matriz de permissões (§6) reproduzida 100% — testes automatizados por papel × ação.
- [ ] Workflow de candidatos com os 7 níveis de revisão funcionando exatamente como hoje.
- [ ] Regras de data/sessão respeitam timezone `America/Sao_Paulo`.
- [ ] `npm run lint`/`pytest` verde; cobertura mínima de 80% nos serviços de negócio.

---

## 3. Decisão de Stack

### 3.1 Stack recomendada (usada no Sprint Plan)

| Camada | Escolha | Justificativa |
|---|---|---|
| Framework | **Django 5.x LTS** | Monólito, admin grátis, ORM maduro, migrações versionadas |
| API interna | **Views Django + Django Templates** (server-rendered) + **HTMX** para interações parciais | Substitui os client components/fetch do Next.js sem SPA |
| Front-end | **Tailwind CSS** (via CLI/standalone) + **Alpine.js** (menus/modais) + **Chart.js** (gráficos, substitui Recharts) + **FullCalendar ou calendário próprio leve** | Paridade visual com o atual |
| Banco | **PostgreSQL 16** | Mesmo banco do legado → migração direta |
| Auth | `django.contrib.auth` + hash **bcrypt** (`PASSWORD_HASHERS` com `BCryptPasswordHasher` primeiro) | **Compatibilidade com os hashes bcrypt custo 10 do legado** — usuários logam sem reset |
| Sessão/API | Sessão Django por cookie (substitui JWT 15min + refresh 7d + CSRF manual — o Django já traz CSRF) | Simplifica; mantém cookies httpOnly |
| Arquivos | `django-storages` + S3-compatible (**Cloudflare R2**, endpoint custom) | Mesmo storage da Chancelaria |
| E-mail | Backend SMTP do Django (`django.core.mail`) | Substitui nodemailer |
| Validação | Forms/Serializers DRF (somente nos endpoints da API externa) | — |
| API externa | **DRF** + autenticação por Service Token custom + `django-ratelimit` + drf-spectacular (OpenAPI/Swagger) | Paridade com `/api/external/*` e `/api/docs` |
| Tarefas | `cron`/management commands (geração de períodos de pagamento, snapshots KPI) | Sem Celular/Celery na fase 1 |
| Testes | `pytest-django` | — |

### 3.2 Alternativa rejeitada (registrada)
- **Django REST Framework + manter o front React/Next**: preservaria a UI, mas mantém o pipeline Node e duas bases de código. Escolhido monólito para reduzir custo operacional.

---

## 4. Arquitetura

### 4.1 Layout do projeto Django

```
saldarer-django/
├── config/                  # settings (base/dev/prod), urls, wsgi/asgi
├── core/                    # Tenant, mixins de escopo, middleware, utils (phone, datas)
├── accounts/                # User, AuthAttempt, RefreshToken→(descartado), convites, login/primeiro acesso
├── organizacional/          # Prefeitura, Potencia, Rito, Loja, Class
├── membros/                 # Member, perfil, datas cavaleirescas, importação
├── candidatos/              # Candidato, CandidatoObservacao, workflow, portal do candidato, súplica
├── presenca/                # Meeting, Attendance, frequência, relatórios, ranking
├── financeiro/              # Categoria, Lancamento, dashboard financeiro
├── pagamentos/              # PaymentPeriod, PaymentStatus, MemberPayment, Payment, DuesCharge, KpiSnapshot, grade
├── inventario/              # InventoryItem, InventoryMovement, export CSV/PDF
├── chancelaria/             # ChancelariaDocument, ChancelariaDocumentEvent, R2
├── dashboard/               # agregações do painel principal
├── api_external/            # DRF: lojas, prefeituras, service tokens, auditoria
├── templates/               # base + por app (herda design system)
└── static/                  # tailwind, chart.js, alpine
```

### 4.2 Padrões obrigatórios
1. **Escopo multi-tenant**: `TenantQuerySet`/`TenantManager` — todo model com `tenant_id` expõe `.for_user(user)` que aplica o escopo (global / prefeitura / loja). Views nunca montam filtros manuais.
2. **Permissões**: decoradores/mixins `role_required(...)` + funções de papel em `core/roles.py` (espelho exato de `lib/roles.ts`).
3. **Auditoria**: app `core.audit` grava `AuditLog` em login e ações sensíveis; `PaymentAuditLog` permanece específico de pagamentos.
4. **Datas**: `TIME_ZONE = "America/Sao_Paulo"`, `USE_TZ = True`. Regra de sessão (`SESSION_NOT_HAPPENED_YET`) usa `timezone.localdate()`.
5. **Erros tipados**: exceções de domínio (`NotFound`, `Conflict`, `Forbidden`) mapeadas para 404/409/403.
6. **Sem middleware Next**: os guards do `AuthEnforcer` (401 → `/login`, `mustChangePassword` → `/senha`, `mustCompleteProfile` → `/primeiro-acesso/completar-cadastro`) viram **middleware Django**.

---

## 5. Nomenclatura Oficial (MUDANÇA IMPORTANTE)

A partir da versão Django, o termo **"Apresentação"** é substituído por **"Recepção"** em toda a interface, e-mails, relatórios e nomes de campos novos.

| Legado (Next.js/Prisma) | Novo (Django) | Rótulo na UI |
|---|---|---|
| `apresentacaoMx` / `apresentacao_mx` ("dataMESA") | `recepcao_mx` | **Data de Recepção MX** — "Recepção a Mestre de Mesa" |
| `apresentacaoEc` / `apresentacao_ec` ("dataEN") | `recepcao_ec` | **Data de Recepção EN** — "Recepção a Escudeiro Noviço" |
| `armaduraCbcs` / `armadura_cbcs` ("dataCBCS") | `armadura_cbcs` (mantém) | Data de Armadura CBCS |
| Colunas "Apresentação (MX)" / "Apresentação (EC)" (ranking/frequência) | idem, com `recepcao_*` | **"Recepção (MX)" / "Recepção (EC)"** |
| Texto "cerimônia de apresentação" (e-mail/telas do candidato) | — | **"cerimônia de recepção"** |
| Texto "quitação da apresentação ao grau" (e-mail do candidato) | — | **"quitação da recepção ao grau"** |
| Campo de ranking `tempoApresentacaoMeses` | `tempo_recepcao_meses` | — |

> A migração de dados renomeia as colunas (`apresentacao_mx → recepcao_mx`, `apresentacao_ec → recepcao_ec`) **preservando os dados** (ver §11).

---

## 6. Papéis e Matriz de Permissões

### 6.1 Papéis (`User.role` — `TextChoices`)
`SYS_ADMIN` (Grão-Mestre) · `GRAO_MESTRE` · `GRANDE_CHANCELER` · `GRANDE_TESOUREIRO` · `GRANDE_SECRETARIO` · `GRANDE_PRIOR` · `PREFEITO` · `ADMIN_LOJA` (Delegado Mestre/DM) · `SECRETARIO_LOJA` · `TESOUREIRO` · `MEMBER` · `CANDIDATO`

### 6.2 Matriz (espelho de `lib/roles.ts` — implementar como funções puras em `core/roles.py` + testes)

| Regra | Papéis |
|---|---|
| `is_saas_admin` | SYS_ADMIN, GRAO_MESTRE, GRANDE_CHANCELER, GRANDE_TESOUREIRO, GRANDE_SECRETARIO, GRANDE_PRIOR |
| `can_manage_prefeituras` / `can_manage_lojas` | SYS_ADMIN, GRANDE_CHANCELER |
| `can_manage_members` (CRUD) | SYS_ADMIN, GRANDE_CHANCELER (+ escopo global via lojas) |
| `can_edit_members` | anteriores + ADMIN_LOJA, SECRETARIO_LOJA (TESOUREIRO só leitura) |
| `can_delete_members` | SYS_ADMIN, GRANDE_CHANCELER, ADMIN_LOJA (escopo loja) |
| `can_view_members` | todos autenticados exceto CANDIDATO |
| `can_view_finance` | is_saas_admin, ADMIN_LOJA, TESOUREIRO, SECRETARIO_LOJA, MEMBER — **GRANDE_PRIOR: NÃO** |
| `can_manage_finance` | TESOUREIRO, is_saas_admin, PREFEITO |
| `can_mutate_payments` | can_manage_finance **exceto GRANDE_CHANCELER** (só leitura) |
| `can_view_member_payment_pages` | bloqueia GRANDE_CHANCELER e PREFEITO |
| `can_access_mensalidades_tab` | MEMBER, ADMIN_LOJA, SECRETARIO_LOJA, TESOUREIRO |
| `can_access_presence` / `can_manage_presence` | != MEMBER / (is_saas_admin, ADMIN_LOJA, SECRETARIO_LOJA) |
| `can_mark_or_delete_presence_at_loja` | ADMIN_LOJA, SECRETARIO_LOJA (TESOUREIRO não) |
| `can_access_chancelaria` | is_saas_admin, PREFEITO, ADMIN_LOJA, SECRETARIO_LOJA, TESOUREIRO, MEMBER |
| `can_delete_chancelaria_document` | SYS_ADMIN, GRANDE_CHANCELER |
| `can_access_inventory` | TESOUREIRO, is_saas_admin, ADMIN_LOJA (movimentações: ADMIN_LOJA/TESOUREIRO; MEMER 403) |
| `can_create_user` / `can_delete_user` | is_saas_admin |
| `can_assign_privileged_org_roles` | SYS_ADMIN, GRANDE_CHANCELER |
| `DELEGADO_MANAGED_ROLES` (o que ADMIN_LOJA gerencia) | MEMBER, TESOUREIRO, SECRETARIO_LOJA |
| Aprovação final de candidato (`pode_aprovar`) | GRANDE_PRIOR, GRAO_MESTRE, SYS_ADMIN |

### 6.3 Escopos de dados
- Loja-restritos (ADMIN_LOJA, SECRETARIO_LOJA, TESOUREIRO, MEMBER): queries fixadas em `user.loja_id`.
- PREFEITO: lojas da própria `prefeitura_id`.
- SaaS-level: visão global; **loja padrão GPRB** para dashboards/caixa (`user_default_scope`).
- Criação de usuário: tenant herdado da loja selecionada; roles SaaS recebem loja GPRB obrigatória.

---

## 7. Modelo de Dados (30 modelos → Django models)

> Convenção: `db_table` igual às tabelas atuais (snake_case do Prisma) para permitir carga direta dos dados. Todos os "enums" viram `models.TextChoices`. Multi-tenant por FK `tenant`.

### 7.1 Núcleo e contas
| Model (tabela) | Campos-chave / constraints |
|---|---|
| **Tenant** `tenant` | `name`, `code?` (unique, ex "GPRB") |
| **User** `user` | `tenant` FK, `email`, `password_hash?` (bcrypt), `role` (default MEMBER), `status` (INVITED/ACTIVE — login só ACTIVE), `loja?` FK (RESTRICT), `prefeitura?` FK, `login_identifier?` (celular normalizado — usado no login), `must_change_password`, `must_complete_profile`, `name?`, `deleted_at?` (soft delete), `last_login_at?`, `created_by/updated_by`; unique `(tenant,email)` |
| **AuditLog** `audit_log` | `tenant`, `loja?`, `user?`, `action` (ex LOGIN), `resource`, `message`, `metadata` JSON |
| **PasswordInviteToken** `password_invite_token` | `user`, `token_hash` unique (SHA-256), `expires_at` (48h), `used_at?`, `code_attempts` (máx 5), `code_hash?` (6 dígitos), `code_validated_at?`, `sent_at/sent_to` |
| **AuthAttempt** `auth_attempt` | rate limit de login: `identifier_hash`, `ip`, `attempts`, `locked_until?` |
| **ServiceToken** `service_token` | API externa: `name`, `token_hash` unique, `prefix` unique, `scopes[]` (read:prefeituras, read:lojas, read:directory), `expires_at?`, `revoked_at?`, `last_used_at?` |
| **ExternalApiAuditLog** `external_api_audit_log` | `token`, `method`, `path`, `query?`, `status_code`, `latency_ms`, `ip?`, `user_agent?`, `error_code?` |

### 7.2 Organizacional
| Model | Especificação |
|---|---|
| **Prefeitura** `prefeitura` | `nome` (unique por tenant), `sigla?`, `regiao?`, `patrono?`, `prefeito?`, `prefeito_nome_ordem?`, `telefone?`, `website?`, endereço completo (opcional), `observacoes?`, `status?` |
| **Potencia** `potencia` | catálogo global: `nome` (max 6) |
| **Rito** `rito` | `sigla` PK, `nome` unique |
| **Loja** `loja` | `loja_mx` (nome), `numero?`, `mensalidade_ativa` (default true), `cnpj?`, contatos, endereço, `data_fundacao?`, `situacao` (default ATIVA), dados bancários (8 campos: banco_nome/codigo/agencia(+dig)/conta(+dig)/pix/tipo_conta), `razao_social?`, `nome_fantasia?`, `data_abertura?`, `mensalidade_regular?` Decimal(10,2), `mensalidade_remido?` Decimal(10,2), `short_name?` **unique** (sincroniza `Tenant.name`), `prefeitura` FK **obrigatória**, `contato_nome?`, `contract_number` (default "PENDENTE"); unique `(prefeitura, numero)` |
| **Class** `class` | grau: `abbreviation` unique (MX, EC, CBCS, SC...), `name`; classe padrão de criação de membro: **MX** |

### 7.3 Membros
**Member** `member` — campos agrupados:
- Identificação: `nome_completo`, `cpf` (obrigatório, unique por tenant), `data_nascimento?`, `pai?`, `mae?`, `natural_cidade?`, `nacionalidade?`, `estado_civil?` (SOLTEIRO/CASADO/DIVORCIADO/VIUVO/UNIAO_ESTAVEL), `identidade_numero?`, `orgao_emissor?`, `data_emissao?`, `foto_url?`
- Contato/endereço: `email`, `celular` (normalizado), `telefone_urgencia?`, `endereco_logradouro/numero/complemento/bairro/cidade/uf/cep`
- Ritualístico: `loja` FK, `class` FK, `cargo?` (default SC), `rito?`, `loja_simbolismo?`, `potencia_simbolismo?`, `data_iniciacao?`, `data_passagem?`, `data_elevacao?`, `data_instalacao?`, `numero_filiado?` (unique por tenant), `tipo_admissao?` (INIC/FILI/READ)
- Situação/financeiro: `situacao` (ATIVO/PROPOSTO/ADORMECIDO), `condicao_mensalidade` (REGULAR/REMIDO — REMIDO sai da grade de mensalidades)
- **Datas cavaleirescas (nova nomenclatura)**: `recepcao_mx?` (← `apresentacao_mx`), `recepcao_ec?` (← `apresentacao_ec`), `armadura_cbcs?`, `loja_mx?`, `loja_ec?`, `loja_cbcs?` (VarChar)
- **Regras**: `data_admissao?`; validação cronológica das datas de recepção (Recepção MX obrigatória na criação; Recepção EN ≥ MX; Armadura CBCS ≥ EN); exclusão em transação: desvincular inventário, apagar PaymentStatus/Payment/DuesCharge/MemberPayment+Lancamento/Attendance/User vinculado → Member.

### 7.4 Candidatos
| Model | Especificação |
|---|---|
| **Candidato** `candidato` | dados pessoais completos (opcionais exceto `nome_completo`), `cpf?` unique por tenant, `grau` (default MX; MX/EC/CBCS), documentos: `comprovante_pagamento?`, `foto?`, `quitacao_url?`, `pagamento_url?`; loja simbólica: `loja_simbolo?`, `numero_loja_simbolo?`, `data_exaltacao?`, `potencia_simbolo?`, `rito_loja_simbolo?`; acesso: `access_token?` unique (hash), `token_expires_at?` (7d), `token_used_at?`, `password_hash?`, `confirmation_code_hash?` (**4 dígitos**), `code_attempts` (máx 5), `code_validated_at?`; `data_inscricao`, `status` (default EM_ANALISE), `revisao_atual?`, `data_aprovacao?`, `data_reprovacao?`, `data_desistencia?`, `data_inicio?`; unique `(tenant, cpf)`; index `(tenant, status)` |
| **CandidatoObservacao** `candidato_observacao` | `candidato` FK cascade, `autor_id`, `autor_nome`, `autor_papel`, `texto` (máx 5000) |

**Status**: `EM_ANALISE, FICHA_ENVIADA, EM_REVISAO, APROVADO, INICIADO, REPROVADO, DESISTIU, DEVOLVIDO_CANDIDATO`
**Níveis de revisão** (`revisao_atual`): `DM → PREFEITO → TESOUREIRO → CHANCELER → PRIOR → CHANCELER_2 → DM_FINAL`; mapa papel→nível: ADMIN_LOJA→DM, PREFEITO→PREFEITO, GRANDE_TESOUREIRO→TESOUREIRO, GRANDE_CHANCELER→CHANCELER, GRANDE_PRIOR→PRIOR. SYS_ADMIN tem bypass.

### 7.5 Presença
| Model | Especificação |
|---|---|
| **Meeting** `meeting` | `tenant`, `loja?` FK, `data_sessao`, `tipo` (ORDINARIA/EXTRAORDINARIA/INICIACAO/INSTALACAO/MAGNA/LUTO), `titulo?`, `descricao?`, `observacoes?` |
| **Attendance** `attendance` | `meeting` FK, `member` FK, `status` (PRESENTE/FALTA/JUSTIFICADA), `observacoes?`; unique `(meeting, member)`; **só registrar em sessões já ocorridas** (TZ São Paulo) |

### 7.6 Financeiro
| Model | Especificação |
|---|---|
| **Categoria** `categoria` | `nome`, `tipo` (RECEITA/DESPESA); unique `(tenant, nome, tipo)`; bloquear exclusão com lançamentos |
| **Lancamento** `lancamento` | `tipo` (RECEITA/DESPESA), `categoria` FK, `descricao`, `valor_previsto`, `valor_pago` (default 0), `data_vencimento`, `data_pagamento?`, `status` (ABERTO/PAGO/PARCIAL/ATRASADO/PREVISTO), `forma_pagamento?` (PIX/TRANSFERENCIA/DINHEIRO/BOLETO), `anexo?` |

### 7.7 Pagamentos de membros e billing
| Model | Especificação |
|---|---|
| **MemberPayment** `member_payment` | pagamento real do membro: `member` FK, `lancamento` 1:1, `payment_type` (MENSALIDADE_LOJA/ANUIDADE_PRIORADO), `reference_month/year?`, `description`, `amount`, `payment_method`, `payment_date`, auditoria |
| **PaymentPeriod** `payment_period` | `type` (MONTHLY/ANNUAL/EVENT), `year`, `month?`, `event_id?`, `label?`; unique `(tenant,type,year,month,event)` |
| **PaymentStatus** `payment_status` | grade membro×período: `status` (PENDING/PAID/CANCELED), `amount?`, `method?` (PIX/DINHEIRO/TRANSFERENCIA/BOLETO/CARTAO/CONVENIO), `paid_at?`, `notes?`; unique `(tenant,member,period)` |
| **PaymentAuditLog** `payment_audit_log` | `action` (MARK_PAID/MARK_PENDING/EDIT_META/CANCEL), `before?`, `after?`, `actor` |
| **Payment** `payment` (billing) | `loja`, `member`, `type` (MONTHLY/ANNUAL), `year`, `month?`, `amount` Decimal, `method`, `status`, `paid_at`, `beneficiary` (obrigatório), `reference?`, `notes?` |
| **DuesCharge** `dues_charge` | cobrança esperada: unique `(tenant,loja,type,year,month,member)`; `expected_amount`, `status` (OPEN/...), `paid_payment` 1:1 |
| **KpiSnapshot** `kpi_snapshot` | por loja/período: `expected/paid/open_amount`, `members_active`, `paid_members`, `delinquent_members`; unique `(tenant,loja,type,year,month)` |

### 7.8 Inventário e Chancelaria
| Model | Especificação |
|---|---|
| **InventoryItem** `inventory_item` | `sku?`, `name`, `unit?`, `category?`, `location?`, `min_qty`, `reorder_point`, `qty_on_hand`, `avg_cost` Decimal, `last_purchase_cost?`, `assigned_to_member?` FK, auditoria completa, arquivamento (`archived_at/by/reason`) |
| **InventoryMovement** `inventory_movement` | `type` (IN/OUT/ADJUST/ARCHIVE), `qty`, `unit_cost?`, `movement_value?`, `qty_before/after`, `avg_cost_before/after`, `reason?`, `ip?`, `user_agent?`. **IN recalcula custo médio**; OUT valida saldo; ADJUST delta não-negativo |
| **ChancelariaDocument** `chancelaria_document` | `direction` (SENT/RECEIVED), `protocol_code` **unique** formato `{PREFIXO5}-{NUM4}-{AA}`, `protocol_number/year`, `title`, `document_date`, `visibility` (PUBLIC/LOJA/PREFEITOS/GPRB/CHANCELER), `document_location` (ATA/EXPEDIENTE/PORTARIA/PA/FOTOGRAFIA/OUTROS), `status` (default ARQUIVADO), storage R2 (`provider/bucket/key`), `file_url/name/mime/size`, `uploaded_at`, auditoria |
| **ChancelariaDocumentEvent** | trilha de eventos do documento (`event_type`, `description`, `from_status?`, `to_status?`) |

---

## 8. Módulos Funcionais

### 8.1 Autenticação e conta
- **Login por celular + senha** (não e-mail). Rate limit + `AuthAttempt` com lock. AuditLog LOGIN.
- Sessão cookie httpOnly + CSRF (nativo Django). `status` só `ACTIVE` loga; loja deve estar ATIVA.
- **Fluxo de convite**: admin cria usuário → senha temporária + `must_change_password` **ou** e-mail com link `/auth/set-password?token=` + **código de 6 dígitos** (48h, máx 5 tentativas, hash SHA-256).
- **Primeiro acesso do membro**: `must_complete_profile` força `/primeiro-acesso/completar-cadastro` (PUT perfil: dados pessoais/documentos/endereço; limpa a flag).
- **Esqueci a senha**: exige **e-mail + celular** conferirem; token + código 6 dígitos; rate limit 3/15min; resposta genérica.
- **Troca de senha** com política forte; re-autenticação de admin (`verify-password`) para ações sensíveis (arquivar item).
- **Portal do candidato**: token de 32 bytes (hash no banco), 7 dias, uso único para definir senha, **código de 4 dígitos**.

### 8.2 Dashboard (`/`)
- KPIs: Lojas ativas, Membros ativos, Sessões no ano, Caixa (anuidades+iniciações do ano, papéis de Grão-Conselho).
- Ações rápidas com gating por papel.
- Gráficos: distribuição por grau (ordem **AP, CM, MM, MI, EC, MX, CBCS, SC, NI**), por potência, por rito, faixas de idade (+mediana), admissões 36 meses (fallback: `data_admissao` → `recepcao_mx` → `created_at`), frequência 24 meses, fluxo de caixa realizado (36m) + projetado (12m), categorias receita/despesa.
- **Mapa das lojas no Brasil** (geocodificação via proxy Nominatim com cache 12h) e **calendário de sessões** com filtro por dia.

### 8.3 Membros
- Listagem: busca, filtros situação/classe/loja, paginação, KPIs; ações por papel.
- CRUD completo com validação de datas cavaleirescas e classe mínima MX; cria `User` MEMBER vinculado (`ensure_member_user`).
- Ficha detalhada em seções; edição; exclusão transacional (§7.3).
- **Datas cavaleirescas**: Recepção MX / Recepção EN / Armadura CBCS + lojas correspondentes.
- Pagamentos do membro: histórico (KPIs) + registro (tipo, mês/ano referência, categoria, valor, forma, data) — cria `Lancamento` RECEITA PAGO + `MemberPayment`.
- Envio de convite de acesso ao membro.

### 8.4 Candidatos (administrativo)
- Listagem com KPIs por status, filtros status/grau, trilha de workflow.
- **Fluxo completo**:
  1. `ADMIN_LOJA` cadastra candidato → `EM_ANALISE`;
  2. envia ficha por e-mail → token + link público; status → `FICHA_ENVIADA`;
  3. candidato preenche a **Súplica** (dados completos + 3 uploads: foto, quitação, comprovante) e envia;
  4. DM aprova (`aprovar-dm`) → `EM_REVISAO` / nível PREFEITO;
  5. encaminhar/devolver avança/recua 1 nível (7 níveis, §7.4), registrando `CandidatoObservacao`;
  6. aprovação final (PRIOR + `pode_aprovar`) → `APROVADO` + `data_aprovacao`;
  7. devolver ao candidato (níveis DM/DM_FINAL) → `DEVOLVIDO_CANDIDATO`;
  8. `INICIADO`: transforma em **Member** (classe MX, `tipo_admissao=INIC`, cargo por grau MX→MX/EC→EC/CBCS→SC) + `User` vinculado; exige CPF, nascimento, sem membro duplicado.
- Observações com autor e papel; histórico visual de 7 níveis na ficha.

### 8.5 Portal do candidato (`/candidato/*`)
- `/candidato/dashboard`: status com descrição/datas; atalho "Terminar a Súplica".
- `/candidato/suplica`: formulário completo, uploads, rascunho (salvar) vs envio (status FICHA_ENVIADA); bloqueio de campos após envio; observações recebidas; tela de sucesso com citação e aviso sobre a **cerimônia de recepção**.

### 8.6 Presença e Ranking
- Sessões: CRUD (6 tipos), KPIs anuais, filtro período/loja; exclusão bloqueada com presenças.
- Marcação em lote por sessão (upsert unique meeting+member), **apenas para sessões ocorridas**; bloqueio visual para futuras; edição só ADMIN_LOJA/SECRETARIO_LOJA.
- Frequência por membro (usada em `/presenca` e `/ranking`): % nos últimos 18 meses (MX) / 12 meses (EC).
- **Ranking ritualístico**: escolha MX ou EC, janela 24 meses, ordena por % + tempo de **recepção**; relatórios por período/por membro com impressão.

### 8.7 Financeiro
- Lançamentos (RECEITA/DESPESA) com categoria, vencimento, pagamento parcial (PARCIAL), status calculados.
- Dashboard financeiro: KPIs a pagar/receber, pago/recebido, saldo previsto/realizado; comparativo ano/mês; fluxo mensal realizado + **previsão de caixa** (expansível); pizza por categoria.
- Categorias: CRUD por tipo com bloqueio de exclusão em uso.

### 8.8 Pagamentos (grade)
- 3 abas: **Mensalidade** (12 meses), **Anuidade**, **Iniciações**; matriz membro × período com totais; botão Pagar (modal) → `PaymentStatus` + auditoria.
- `mark`: PENDING/PAID/CANCELED; **GRANDE_CHANCELER não muta**; aba Mensalidade restrita (§6.2).
- `register`: cria Lancamento RECEITA PAGO + MemberPayment (categoria auto "Mensalidades"/"Anuidades").
- Membros REMIDO saem da grade mensal; MEMBER vê só a própria linha.
- Billing (legado mantido): Payment/DuesCharge/KpiSnapshot + `billing/summary`, `dues/matrix`, export CSV.

### 8.9 Inventário
- Itens com estoque mínimo/reorder; filtros (busca, atribuído, abaixo do mínimo, arquivados); KPIs; **export CSV/PDF**.
- Movimentações IN (custo médio), OUT (valida saldo), ADJUST; detalhe com histórico.
- **Arquivamento exige re-autenticação por senha + motivo**.
- `/meu-material`: itens atribuídos ao membro logado.

### 8.10 Chancelaria
- Documentos SENT/RECEIVED com protocolo `{PREFIXO5}-{NUM4}-{AA}`, upload R2, download respeitando visibilidade, eventos, exclusão só SYS_ADMIN/GRANDE_CHANCELER.
- Abas por direção; visibilidade em camadas por papel (PUBLIC/LOJA/PREFEITOS/GPRB/CHANCELER).

### 8.11 Organizacional (Prefeituras e Lojas)
- Prefeituras: CRUD completo (Server Actions → views POST), exclusão bloqueada com lojas; visões restritas (§6.3).
- Lojas: CRUD com validação CNPJ, `short_name` único (checa `Tenant.name`; sincroniza ao editar), prefixo "Grande Priorado -"/"GP-" no tenant GPRB, dados bancários, mensalidades regular/remida; exclusão bloqueada com vínculos; modal de membros da loja; `/api/lojas/{id}/valores` (fallbacks anuidade 500 / mensalidade 150/150).

### 8.12 Usuários
- Listagem com filtros e último acesso (AuditLog); criação com senha temporária ou convite; edição com opções de papel conforme ator; exclusão (não a si mesmo; não privileged sem permissão); reenvio de convite.

### 8.13 API externa (DRF)
- `GET /external/lojas`, `GET /external/prefeituras`, `GET /external/prefeituras/{id}/lojas` — **Service Token** Bearer (prefix + hash SHA-256), scopes `read:lojas`/`read:prefeituras`/`read:directory`, CORS, rate limit 60/min global e 30/min por token, `ExternalApiAuditLog`.
- OpenAPI (drf-spectacular) + Swagger UI.
- Health: `/health` (banco ok/degraded) e `/ready` (503 se banco down).
- Geocode proxy (Nominatim, cache 12h).

### 8.14 E-mails transacionais (templates)
1. Convite de criação de senha (usuário) — link + código 6 dígitos.
2. Recuperação de senha — link + código.
3. Ficha enviada (candidato) — link da súplica.
4. Acesso do candidato — link + **código de 4 dígitos** + checklist (inclui **"recibo de quitação da recepção ao grau pretendido"**).

---

## 9. Fluxos Críticos (ponta a ponta)

1. **Onboarding de usuário**: admin cria → senha temporária/convite → primeiro login → troca obrigatória → completar perfil → uso normal.
2. **Admissão de candidato** (§8.4) — o fluxo de negócio mais complexo; deve ter paridade exata de status e permissões.
3. **Ciclo mensal de mensalidades**: geração de períodos → grade → marcação/registro → Lancamento/MemberPayment → dashboards.
4. **Sessão ritualística**: criar sessão → realizar → marcar presenças → alimentar frequência/ranking → relatórios.
5. **Entrada de material**: item → IN com custo → custo médio recalculado → atribuição a membro → `/meu-material`.
6. **Documento de chancelaria**: upload → protocolo → trilha → download visível conforme papel.

---

## 10. Requisitos Não Funcionais

| Requisito | Especificação |
|---|---|
| Multi-tenancy | Isolamento por `tenant_id` em managers; testes automatizados anti-vazamento |
| Segurança | CSRF nativo; cookies httpOnly/secure; rate limits (login, forgot 3/15min, API externa); bcrypt; política de senha forte; validação server-side em todos os forms |
| Timezone | `America/Sao_Paulo` para regra de sessão, relatórios e agregações SQL |
| Auditoria | AuditLog (auth + sensíveis), PaymentAuditLog, ChancelariaDocumentEvent, ExternalApiAuditLog, InventoryMovement (ip/user-agent) |
| Arquivos | R2 (S3) com chaves sanitizadas; uploads validados (mime/tamanho) |
| E-mails | SMTP; templates HTML com escape; modo console em dev |
| Observabilidade | `/health`, `/ready`; logging estruturado |
| Performance | Paginação em todas as listas (máx 100); `select_related/prefetch` nos agregados; índices conforme schema |
| Acessibilidade | Manter padrões do legado (labels, contraste dark, foco) |
| Compat. de senhas | Hashers: BCrypt primeiro → migração sem reset de senha |

---

## 11. Migração de Dados

1. **Banco**: reaproveitar o PostgreSQL existente. Models Django mapeiam `db_table`/`db_column` atuais.
2. **Renomeação controlada**: migração Django `RenameField` de `apresentacao_mx → recepcao_mx` e `apresentacao_ec → recepcao_ec` (dados preservados). (Opcional: views de compatibilidade durante o transição.)
3. **Carga**: `pg_dump`/`restore` do ambiente de produção → homologação; validar contagens por tabela e totais financeiros contra o legado.
4. **Senhas**: bcrypt custo 10 — compatível com `BCryptPasswordHasher`.
5. **Arquivos**: chaves R2 inalteradas.
6. **Plano de corte (cutover)**: manter legado em modo leitura → restore final → smoke tests (login, ficha de membro, grade de pagamentos, protocolo de chancelaria) → DNS.

---

## 12. Fora de escopo (placeholders mantidos)
`/quiz`, `/comunicacao`, `/biblioteca`, `/mensalidades` (placeholder) — reproduzir como páginas "em desenvolvimento". Rotas stub 501 do legado (`/api/candidato-acesso/*`, `/api/candidato/suplica` como API) **não** serão portadas: a lógica real vive nas views do portal do candidato.

## 13. Riscos
| Risco | Mitigação |
|---|---|
| Regressão no workflow de 7 níveis | Testes de integração por nível × papel com fixture de candidato |
| Perda de comportamento de escopo | Testes parametrizados papel × queryset (`for_user`) |
| Incompatibilidade de senhas | Hasher BCrypt validado em homologação com cópia real do banco |
| Datas/horário (TZ) nas presenças | Testes com sessões no fuso e fronteira de meia-noite |
| Gráficos/mapa com paridade inferior | Chart.js + proxy geocode mantidos; validar com dados reais |

---

*Ver o plano de execução detalhado em `DOCS/SPRINT-PLAN-DJANGO.md`.*
