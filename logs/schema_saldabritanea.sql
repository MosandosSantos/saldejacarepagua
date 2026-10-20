-- ===== tenant =====
CREATE TABLE public."tenant" (
    "id" text NOT NULL,
    "name" text NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL,
    "code" text,
    PRIMARY KEY ("id")
);

-- ===== user =====
CREATE TABLE public."user" (
    "id" text NOT NULL,
    "tenantId" text NOT NULL,
    "email" text NOT NULL,
    "passwordHash" text,
    "role" text DEFAULT 'MEMBER'::text NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL,
    "createdByUserId" text,
    "lojaId" text,
    "status" text DEFAULT 'INVITED'::text NOT NULL,
    "updatedByUserId" text,
    "deletedAt" timestamp(3) without time zone,
    "lastLoginAt" timestamp(3) without time zone,
    "loginIdentifier" text,
    "mustChangePassword" boolean DEFAULT false NOT NULL,
    "mustCompleteProfile" boolean DEFAULT false NOT NULL,
    "name" text,
    "prefeituraId" text,
    PRIMARY KEY ("id")
);
ALTER TABLE public."user" ADD CONSTRAINT "user_tenantId_fkey" FOREIGN KEY ("tenantId") REFERENCES tenant(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE public."user" ADD CONSTRAINT "user_lojaId_fkey" FOREIGN KEY ("lojaId") REFERENCES loja(id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE public."user" ADD CONSTRAINT "user_prefeituraId_fkey" FOREIGN KEY ("prefeituraId") REFERENCES prefeitura(id) ON UPDATE CASCADE ON DELETE RESTRICT;

-- ===== member =====
CREATE TABLE public."member" (
    "id" text NOT NULL,
    "tenantId" text NOT NULL,
    "lojaId" text,
    "rito" text,
    "dataAdmissao" timestamp(3) without time zone,
    "tipoAdmissao" text,
    "numeroFiliado" text,
    "nomeCompleto" text NOT NULL,
    "dataNascimento" timestamp(3) without time zone,
    "pai" text,
    "mae" text,
    "naturalCidade" text,
    "nacionalidade" text,
    "estadoCivil" text,
    "identidadeNumero" text,
    "orgaoEmissor" text,
    "dataEmissao" timestamp(3) without time zone,
    "cpf" text NOT NULL,
    "email" text NOT NULL,
    "celular" text NOT NULL,
    "telefoneUrgencia" text,
    "enderecoLogradouro" text NOT NULL,
    "enderecoCep" text NOT NULL,
    "enderecoBairro" text,
    "enderecoCidade" text NOT NULL,
    "enderecoUf" text NOT NULL,
    "escolaridade" text,
    "dataIniciacao" timestamp(3) without time zone,
    "dataPassagem" timestamp(3) without time zone,
    "dataElevacao" timestamp(3) without time zone,
    "dataInstalacao" timestamp(3) without time zone,
    "situacao" text DEFAULT 'ATIVO'::text NOT NULL,
    "fotoUrl" text,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL,
    "enderecoComplemento" text,
    "enderecoNumero" text,
    "cargo" text DEFAULT 'SC'::text,
    "condicao_mensalidade" text DEFAULT 'REGULAR'::text NOT NULL,
    "apresentacao_ec" timestamp(3) without time zone,
    "apresentacao_mx" timestamp(3) without time zone,
    "armadura_cbcs" timestamp(3) without time zone,
    "loja_cbcs" character varying(30),
    "loja_ec" character varying(30),
    "loja_mx" character varying(30),
    "loja_simbolismo" character varying(50),
    "potencia_simbolismo" character varying(50),
    PRIMARY KEY ("id")
);
ALTER TABLE public."member" ADD CONSTRAINT "member_tenantId_fkey" FOREIGN KEY ("tenantId") REFERENCES tenant(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE public."member" ADD CONSTRAINT "member_lojaId_fkey" FOREIGN KEY ("lojaId") REFERENCES loja(id) ON UPDATE CASCADE ON DELETE RESTRICT;

-- ===== member_loja =====
CREATE TABLE public."member_loja" (
    "memberId" text NOT NULL,
    "lojaId" text NOT NULL,
    "dataInclusao" date DEFAULT CURRENT_DATE NOT NULL,
    "createdAt" timestamp without time zone DEFAULT now() NOT NULL,
    "updatedAt" timestamp without time zone DEFAULT now() NOT NULL,
    PRIMARY KEY ("memberId", "lojaId")
);
ALTER TABLE public."member_loja" ADD CONSTRAINT "member_loja_lojaId_fkey" FOREIGN KEY ("lojaId") REFERENCES loja(id) ON DELETE CASCADE;
ALTER TABLE public."member_loja" ADD CONSTRAINT "member_loja_memberId_fkey" FOREIGN KEY ("memberId") REFERENCES member(id) ON DELETE CASCADE;

-- ===== loja =====
CREATE TABLE public."loja" (
    "id" text NOT NULL,
    "tenantId" text NOT NULL,
    "lojaMX" text NOT NULL,
    "numero" integer,
    "mensalidadeAtiva" boolean DEFAULT true NOT NULL,
    "cnpj" text,
    "email" text,
    "telefone" text,
    "website" text,
    "enderecoLogradouro" text,
    "enderecoNumero" text,
    "enderecoComplemento" text,
    "enderecoBairro" text,
    "enderecoCidade" text,
    "enderecoUf" text,
    "enderecoCep" text,
    "dataFundacao" timestamp(3) without time zone,
    "situacao" text DEFAULT 'ATIVA'::text NOT NULL,
    "observacoes" text,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL,
    "bancoAgencia" text,
    "bancoAgenciaDigito" text,
    "bancoCodigo" text,
    "bancoConta" text,
    "bancoContaDigito" text,
    "bancoNome" text,
    "bancoPix" text,
    "bancoTipoConta" text,
    "nomeFantasia" text,
    "dataAbertura" timestamp(3) without time zone,
    "razaoSocial" text,
    "mensalidade_regular" numeric(10,2),
    "mensalidade_remido" numeric(10,2),
    "short_name" text,
    "prefeituraId" text NOT NULL,
    "contatoNome" text,
    "contractNumber" text DEFAULT 'PENDENTE'::text NOT NULL,
    PRIMARY KEY ("id")
);
ALTER TABLE public."loja" ADD CONSTRAINT "loja_tenantId_fkey" FOREIGN KEY ("tenantId") REFERENCES tenant(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE public."loja" ADD CONSTRAINT "loja_prefeituraId_fkey" FOREIGN KEY ("prefeituraId") REFERENCES prefeitura(id) ON UPDATE CASCADE ON DELETE RESTRICT;

-- ===== prefeitura =====
CREATE TABLE public."prefeitura" (
    "id" text NOT NULL,
    "tenantId" text NOT NULL,
    "nome" text NOT NULL,
    "sigla" text,
    "prefeito" text,
    "telefone" text,
    "email" text,
    "secretarioEmail" text,
    "secretarioTelefone" text,
    "tesoureiroEmail" text,
    "tesoureiroTelefone" text,
    "pix" text,
    "valorAnuidade" numeric(12,2),
    "dataVencimentoAnuidade" date,
    "website" text,
    "enderecoLogradouro" text,
    "enderecoNumero" text,
    "enderecoComplemento" text,
    "enderecoBairro" text,
    "enderecoCidade" text,
    "enderecoUf" text,
    "enderecoCep" text,
    "observacoes" text,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL,
    "patrono" text,
    "prefeitoNomeOrdem" text,
    "status" text,
    PRIMARY KEY ("id")
);
ALTER TABLE public."prefeitura" ADD CONSTRAINT "prefeitura_tenantId_fkey" FOREIGN KEY ("tenantId") REFERENCES tenant(id) ON UPDATE CASCADE ON DELETE CASCADE;

-- ===== potencia =====
CREATE TABLE public."potencia" (
    "id" text NOT NULL,
    "nome" character varying(6) NOT NULL,
    PRIMARY KEY ("id")
);

-- ===== rito =====
CREATE TABLE public."rito" (
    "nome" text NOT NULL,
    "sigla" text NOT NULL,
    PRIMARY KEY ("sigla")
);

-- ===== payment =====
CREATE TABLE public."payment" (
    "id" text NOT NULL,
    "tenantId" text NOT NULL,
    "lojaId" text NOT NULL,
    "memberId" text NOT NULL,
    "type" text NOT NULL,
    "year" integer NOT NULL,
    "month" integer,
    "amount" numeric(65,30) NOT NULL,
    "method" text NOT NULL,
    "status" text NOT NULL,
    "paidAt" timestamp(3) without time zone NOT NULL,
    "createdByUserId" text,
    "reference" text,
    "notes" text,
    "beneficiary" text NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL,
    PRIMARY KEY ("id")
);
ALTER TABLE public."payment" ADD CONSTRAINT "payment_tenantId_fkey" FOREIGN KEY ("tenantId") REFERENCES tenant(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE public."payment" ADD CONSTRAINT "payment_lojaId_fkey" FOREIGN KEY ("lojaId") REFERENCES loja(id) ON UPDATE CASCADE ON DELETE RESTRICT;
ALTER TABLE public."payment" ADD CONSTRAINT "payment_memberId_fkey" FOREIGN KEY ("memberId") REFERENCES member(id) ON UPDATE CASCADE ON DELETE RESTRICT;

-- ===== payment_period =====
CREATE TABLE public."payment_period" (
    "id" text NOT NULL,
    "tenantId" text NOT NULL,
    "type" text NOT NULL,
    "year" integer NOT NULL,
    "month" integer,
    "eventId" text,
    "label" text,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY ("id")
);
ALTER TABLE public."payment_period" ADD CONSTRAINT "payment_period_tenantId_fkey" FOREIGN KEY ("tenantId") REFERENCES tenant(id) ON UPDATE CASCADE ON DELETE CASCADE;

-- ===== payment_status =====
CREATE TABLE public."payment_status" (
    "id" text NOT NULL,
    "tenantId" text NOT NULL,
    "memberId" text NOT NULL,
    "periodId" text NOT NULL,
    "status" text DEFAULT 'PENDING'::text NOT NULL,
    "amount" double precision,
    "method" text,
    "paidAt" timestamp(3) without time zone,
    "notes" text,
    "updatedById" text,
    "updatedAt" timestamp(3) without time zone NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY ("id")
);
ALTER TABLE public."payment_status" ADD CONSTRAINT "payment_status_memberId_fkey" FOREIGN KEY ("memberId") REFERENCES member(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE public."payment_status" ADD CONSTRAINT "payment_status_periodId_fkey" FOREIGN KEY ("periodId") REFERENCES payment_period(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE public."payment_status" ADD CONSTRAINT "payment_status_tenantId_fkey" FOREIGN KEY ("tenantId") REFERENCES tenant(id) ON UPDATE CASCADE ON DELETE CASCADE;

-- ===== meeting =====
CREATE TABLE public."meeting" (
    "id" text NOT NULL,
    "tenantId" text NOT NULL,
    "lojaId" text,
    "dataSessao" timestamp(3) without time zone NOT NULL,
    "tipo" text NOT NULL,
    "titulo" text,
    "descricao" text,
    "observacoes" text,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL,
    PRIMARY KEY ("id")
);
ALTER TABLE public."meeting" ADD CONSTRAINT "meeting_tenantId_fkey" FOREIGN KEY ("tenantId") REFERENCES tenant(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE public."meeting" ADD CONSTRAINT "meeting_lojaId_fkey" FOREIGN KEY ("lojaId") REFERENCES loja(id) ON UPDATE CASCADE ON DELETE SET NULL;

-- ===== attendance =====
CREATE TABLE public."attendance" (
    "id" text NOT NULL,
    "tenantId" text NOT NULL,
    "meetingId" text NOT NULL,
    "memberId" text NOT NULL,
    "status" text NOT NULL,
    "observacoes" text,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL,
    PRIMARY KEY ("id")
);
ALTER TABLE public."attendance" ADD CONSTRAINT "attendance_tenantId_fkey" FOREIGN KEY ("tenantId") REFERENCES tenant(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE public."attendance" ADD CONSTRAINT "attendance_meetingId_fkey" FOREIGN KEY ("meetingId") REFERENCES meeting(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE public."attendance" ADD CONSTRAINT "attendance_memberId_fkey" FOREIGN KEY ("memberId") REFERENCES member(id) ON UPDATE CASCADE ON DELETE CASCADE;

