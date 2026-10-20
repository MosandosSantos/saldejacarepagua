-- ============================================================
-- Tabela `class` (graus cavaleirescos) — banco saldogprb (PostgreSQL)
-- Extraída de: public.class em 2026-09-08
-- Deve ser criada ANTES de member (FK member.class_id -> class.id)
-- ============================================================

CREATE TABLE IF NOT EXISTS class (
  abbreviation varchar(4) NOT NULL,
  name         varchar(70) NOT NULL,
  id           uuid        NOT NULL DEFAULT gen_random_uuid(),

  CONSTRAINT class_pkey PRIMARY KEY (id)
);

CREATE UNIQUE INDEX IF NOT EXISTS class_abbreviation_key
  ON public.class USING btree (abbreviation);

-- Dados atuais da origem (3 graus) — opcional; mantenha os mesmos UUIDs
-- para que as FKs de member.class_id continuem válidas na migração.
INSERT INTO class (id, abbreviation, name) VALUES
  ('d5fa6140-8f3c-4180-98a6-62701402ca44', 'CBCS', 'Cavaleiro Benfeitor da Cidade Santa'),
  ('13e753ea-0d8f-48f3-9670-9e94ba188677', 'EN',   'Escudeiro Noviço'),
  ('f7cd3870-1bce-48c3-8bc1-4b57e4cb1490', 'MX',   'Mestre de Santo André')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- Tabela `member` — banco saldogprb (PostgreSQL)
-- Extraída de: public.member em 2026-09-08
--
-- PRÉ-REQUISITO: as tabelas referenciadas pelas FKs devem existir antes:
--   tenant, loja, class (class está acima; tenant e loja ainda precisam
--   existir antes de rodar este arquivo)
-- ============================================================

CREATE TABLE IF NOT EXISTS member (
  id                   text        NOT NULL,
  "tenantId"           text        NOT NULL,
  "lojaId"             text        NOT NULL,
  rito                 text        NULL,
  "dataAdmissao"       timestamp   NULL,
  "tipoAdmissao"       text        NULL,
  "numeroFiliado"      text        NULL,
  "nomeCompleto"       text        NOT NULL,
  "dataNascimento"     timestamp   NULL,
  pai                  text        NULL,
  mae                  text        NULL,
  "naturalCidade"      text        NULL,
  nacionalidade        text        NULL,
  "estadoCivil"        text        NULL,
  "identidadeNumero"   text        NULL,
  "orgaoEmissor"       text        NULL,
  "dataEmissao"        timestamp   NULL,
  cpf                  text        NOT NULL,
  email                text        NOT NULL,
  celular              text        NOT NULL,
  "telefoneUrgencia"   text        NULL,
  "enderecoLogradouro" text        NOT NULL,
  "enderecoCep"        text        NOT NULL,
  "enderecoBairro"     text        NULL,
  "enderecoCidade"     text        NOT NULL,
  "enderecoUf"         text        NOT NULL,
  escolaridade         text        NULL,
  "dataIniciacao"      timestamp   NULL,
  "dataPassagem"       timestamp   NULL,
  "dataElevacao"       timestamp   NULL,
  "dataInstalacao"     timestamp   NULL,
  situacao             text        NOT NULL DEFAULT 'ATIVO'::text,
  "fotoUrl"            text        NULL,
  "createdAt"          timestamp   NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt"          timestamp   NOT NULL,
  "enderecoComplemento" text       NULL,
  "enderecoNumero"     text        NULL,
  cargo                text        NULL DEFAULT 'SC'::text,
  condicao_mensalidade text        NOT NULL DEFAULT 'REGULAR'::text,
  class_id             uuid        NOT NULL,
  apresentacao_ec      timestamp   NULL,
  apresentacao_mx      timestamp   NULL,
  armadura_cbcs        timestamp   NULL,
  loja_cbcs            varchar(30) NULL,
  loja_ec              varchar(30) NULL,
  loja_mx              varchar(30) NULL,
  loja_simbolismo      varchar(50) NULL,
  potencia_simbolismo  varchar(50) NULL,

  CONSTRAINT member_pkey PRIMARY KEY (id),
  CONSTRAINT member_class_id_fkey FOREIGN KEY (class_id)
    REFERENCES class(id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT member_lojaId_fkey FOREIGN KEY ("lojaId")
    REFERENCES loja(id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT member_tenantId_fkey FOREIGN KEY ("tenantId")
    REFERENCES tenant(id) ON UPDATE CASCADE ON DELETE CASCADE
);

-- ============================================================
-- Índices (na ordem exata do banco de origem)
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_member_loja_situacao
  ON public.member USING btree ("lojaId", situacao);
CREATE INDEX IF NOT EXISTS idx_member_tenant_class
  ON public.member USING btree ("tenantId", class_id);
CREATE INDEX IF NOT EXISTS idx_member_tenant_iniciacao
  ON public.member USING btree ("tenantId", "dataIniciacao");
CREATE INDEX IF NOT EXISTS idx_member_tenant_nascimento
  ON public.member USING btree ("tenantId", "dataNascimento");
CREATE INDEX IF NOT EXISTS idx_member_tenant_rito
  ON public.member USING btree ("tenantId", rito);
CREATE INDEX IF NOT EXISTS idx_member_tenant_situacao
  ON public.member USING btree ("tenantId", situacao);
CREATE INDEX IF NOT EXISTS member_class_id_idx
  ON public.member USING btree (class_id);
CREATE INDEX IF NOT EXISTS member_cpf_idx
  ON public.member USING btree (cpf);
CREATE INDEX IF NOT EXISTS "member_lojaId_idx"
  ON public.member USING btree ("lojaId");
CREATE INDEX IF NOT EXISTS member_situacao_idx
  ON public.member USING btree (situacao);

-- Únicos
CREATE UNIQUE INDEX IF NOT EXISTS member_tenantId_cpf_key
  ON public.member USING btree ("tenantId", cpf);
CREATE UNIQUE INDEX IF NOT EXISTS member_tenantId_numeroFiliado_key
  ON public.member USING btree ("tenantId", "numeroFiliado");
CREATE UNIQUE INDEX IF NOT EXISTS member_tenantId_nomeCompleto_idx
  ON public.member USING btree ("tenantId", "nomeCompleto");

-- ============================================================
-- Pagamentos de ANUIDADE e MENSALIDADE — banco saldogprb
-- Extraídas de: public.payment_period / public.payment_status em 2026-09-08
-- Modelo: grade membro × período. Depende de: tenant, member.
-- ============================================================

CREATE TABLE IF NOT EXISTS payment_period (
  id         text      NOT NULL,
  "tenantId" text      NOT NULL,
  type       text      NOT NULL,            -- MONTHLY | ANNUAL | EVENT
  year       integer   NOT NULL,
  month      integer   NULL,                -- só MONTHLY (1-12)
  "eventId"  text      NULL,                -- só EVENT
  label      text      NULL,                -- ex: 'Anuidade 2026', 'Mensalidade jan./2025'
  "createdAt" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT payment_period_pkey PRIMARY KEY (id),
  CONSTRAINT payment_period_tenantId_fkey FOREIGN KEY ("tenantId")
    REFERENCES tenant(id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS "payment_period_tenantId_type_year_idx"
  ON public.payment_period USING btree ("tenantId", type, year);
CREATE UNIQUE INDEX IF NOT EXISTS "payment_period_tenantId_type_year_month_eventId_key"
  ON public.payment_period USING btree ("tenantId", type, year, month, "eventId");

CREATE TABLE IF NOT EXISTS payment_status (
  id           text      NOT NULL,
  "tenantId"   text      NOT NULL,
  "memberId"   text      NOT NULL,
  "periodId"   text      NOT NULL,
  status       text      NOT NULL DEFAULT 'PENDING'::text,  -- PENDING | PAID | CANCELED
  amount       double precision NULL,
  method       text      NULL,            -- PIX | TRANSFERENCIA | DINHEIRO | BOLETO | CARTAO | CONVENIO
  "paidAt"     timestamp NULL,
  notes        text      NULL,
  "updatedById" text     NULL,
  "updatedAt"  timestamp NOT NULL,
  "createdAt"  timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT payment_status_pkey PRIMARY KEY (id),
  CONSTRAINT payment_status_tenantId_fkey FOREIGN KEY ("tenantId")
    REFERENCES tenant(id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT payment_status_memberId_fkey FOREIGN KEY ("memberId")
    REFERENCES member(id) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT payment_status_periodId_fkey FOREIGN KEY ("periodId")
    REFERENCES payment_period(id) ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ps_tenant_period_status
  ON public.payment_status USING btree ("tenantId", "periodId", status);
CREATE INDEX IF NOT EXISTS "payment_status_status_paidAt_idx"
  ON public.payment_status USING btree (status, "paidAt");
CREATE INDEX IF NOT EXISTS "payment_status_tenantId_memberId_idx"
  ON public.payment_status USING btree ("tenantId", "memberId");
CREATE INDEX IF NOT EXISTS "payment_status_tenantId_periodId_idx"
  ON public.payment_status USING btree ("tenantId", "periodId");
-- 1 status por membro por período (a grade)
CREATE UNIQUE INDEX IF NOT EXISTS "payment_status_tenantId_memberId_periodId_key"
  ON public.payment_status USING btree ("tenantId", "memberId", "periodId");

-- =====================================================================
-- RITOS E POTÊNCIAS (tabelas de domínio)
-- =====================================================================

-- ---------------------------------------------------------------------
-- rito — domínio dos ritos maçônicos
-- PK = sigla (ex.: 'REAA'); nome único
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.rito (
  nome  text NOT NULL,
  sigla text NOT NULL,

  CONSTRAINT rito_pkey PRIMARY KEY (sigla)
);

CREATE UNIQUE INDEX IF NOT EXISTS rito_nome_key
  ON public.rito USING btree (nome);

-- Dados atuais da origem (7 ritos) — manter as siglas: member.rito referencia a SIGLA
INSERT INTO rito (nome, sigla) VALUES
  ('Adonhiramita', 'ADON'),
  ('Brasileiro', 'BRAS'),
  ('Emulação', 'EMUL'),
  ('Rito Escocês Antigo e Aceito', 'REAA'),
  ('Rito Escocês Retificado', 'RER'),
  ('Schroeder', 'SHOR'),
  ('York', 'YORK')
ON CONFLICT (sigla) DO NOTHING;

-- ---------------------------------------------------------------------
-- potencia — domínio das Potências maçônicas (GOB, COMAB, CSMB)
-- PK = id (UUID em texto); nome NÃO é único na origem (há IDs duplicados
-- por nome — possível legado de dados)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.potencia (
  id   text NOT NULL,
  nome varchar(6) NOT NULL,

  CONSTRAINT potencia_pkey PRIMARY KEY (id)
);

-- Dados atuais da origem (6 rows, 3 nomes distintos)
INSERT INTO potencia (id, nome) VALUES
  ('3e097dd5-9ed5-4e01-82b7-4e34620acbd6', 'GOB'),
  ('670af0a5-d7a4-4e0d-b0ad-40faa800d75a', 'COMAB'),
  ('7360267a-275d-49b8-9589-238fe4012a2d', 'CSMB'),
  ('7d90156b-d002-46f3-a122-32c084681ae5', 'GOB'),
  ('8dc7c4c2-00ea-4a35-a737-e68a03c2bf44', 'CSMB'),
  ('d7cbd75b-ad34-4cb1-95f2-914967a6df20', 'COMAB')
ON CONFLICT (id) DO NOTHING;

