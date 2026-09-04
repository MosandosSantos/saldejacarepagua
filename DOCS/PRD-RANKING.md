# PRD — Módulo Ranking de Presença (Portátil)

> Documento extra-detalhado para replicar o módulo de **Ranking** (tela + lógica de cálculo) do SALDARER em outra aplicação Next.js (App Router) + Prisma.
> Cada sprint contém o código real usado, a estrutura das funções e os critérios de aceite.

---

## 1. Visão geral

### 1.1 Problema
Listar membros ativos por função (Mestre de Mesa — MX — ou Escudeiro Noviço — EC) ordenados por um ranking composto, considerando tempo de apresentação, presença mínima em sessões e idade como critério de desempate, com visão de frequência sessão-a-sessão (matriz membro × sessão).

### 1.2 Solução atual
- **Tela `/ranking`**: Server Component (guarda de acesso + escopo) + Client Component (filtros, KPIs) que embute a `AttendanceFrequencyTable` em modo "apresentação/ranking".
- **API `/api/presenca/frequencia`**: devolve `{ meetings, members, attendances, memberStats }` já filtrado por tenant/loja/período/classes e **apenas sessões já realizadas**.
- **API `/api/presenca/relatorios?tipo=ranking`**: ranking simples de assiduidade por % de presença (usado nos relatórios, não na tela `/ranking`).
- **Regras de negócio puras** (`session-rules.ts`, `presenca-scope.ts`, `roles.ts`) isoladas em `src/lib` — testáveis e portáveis.

### 1.3 Fora de escopo
Marcação/edição de presença, cadastro de sessões, export PDF/CSV.

---

## 2. Glossário de domínio

| Termo | Significado |
|---|---|
| **Tenant** | Organização (multi-tenant). Todo dado carrega `tenantId`. |
| **Loja** | Unidade (filial) dentro do tenant. Membro pertence a exatamente 1 loja. |
| **Sessão / Meeting** | Reunião com `dataSessao`, `tipo`, `titulo`, opcionalmente ligada a uma loja. |
| **Attendance** | Registro `(meetingId, memberId)` único, com `status`: `PRESENTE` \| `FALTA` \| `JUSTIFICADA`. |
| **Class** | Classe cavaleiresca (tabela `class`, PK `abbreviation` até 4 chars). Ex.: `MX`, `EC`. |
| **Apresentação** | Data em que o membro assumiu a função: `apresentacaoMx` (DateTime?) ou `apresentacaoEc` (DateTime?). |
| **meetsTime** | Membro cujo tempo de apresentação ≥ limiar (12 meses EC / 18 meses MX). |

---

## 3. Requisitos funcionais

| ID | Requisito |
|---|---|
| RF-01 | Acessível apenas a papéis com permissão de presença (admin SaaS, admin loja, secretaria, tesouraria, admin potência, SYS_ADMIN, MEMBER). |
| RF-02 | MEMBER vê **apenas o próprio registro** no ranking; perfis de loja ficam presos à própria loja; perfis globais podem filtrar loja ou ver todas. |
| RF-03 | Período fixo de cálculo: **últimos 24 meses** (1º de janeiro do ano `atual − 2` até hoje). |
| RF-04 | Seleção de classe via rádio: `MX` ou `EC` (uma por vez). |
| RF-05 | KPIs no topo: total no ranking, total EC, total MX (membros ATIVOS no escopo). |
| RF-06 | Tabela matriz membro × sessão com colunas fixas sticky: `RK`, `Nome`, `Apresentação (MX/EC)`. |
| RF-07 | Ordenação padrão do ranking (critérios em §8.2); classificável por apresentação, % e total. |
| RF-08 | % colorido: ≥75 verde, ≥50 âmbar, <50 vermelho. |
| RF-09 | Legenda de status: Presente ✓, Falta ✗, Justificada ⚠, Sem registro —. |
| RF-10 | Paginação de 20 membros/página com RK global (posição absoluta no ranking). |
| RF-11 | Somente sessões **já realizadas** (`dataSessao <= hoje`, normalizado para início do dia, TZ São Paulo) entram no cálculo. |
| RF-12 | Multi-tenant: toda query filtra `tenantId`; `lojaId` do query param é validado contra o tenant. |

## 4. Requisitos não funcionais

| ID | Requisito |
|---|---|
| RNF-01 | TypeScript strict; Server Components para dados sensíveis, Client Components só para interatividade. |
| RNF-02 | Requisições autenticadas (JWT/session) — API retorna 401/403/404 conforme guardas. |
| RNF-03 | Cálculo de estatísticas em memória via `Map` chave `memberId_meetingId` (O(M×S) aceitável para volumes de loja). |
| RNF-04 | Dark theme com tokens `obs-*` (Tailwind v4); variante esmeralda `emeraldTone` na página Ranking. |
| RNF-05 | Datas exibidas em `pt-BR` via `Intl.DateTimeFormat`. |

---

## 5. Modelo de dados (Prisma)

Schema mínimo portátil (extraído de `app/prisma/schema.prisma`):

```prisma
model Member {
  id               String       @id @default(uuid())
  tenantId         String
  lojaId           String
  nomeCompleto     String
  dataNascimento   DateTime?    // usado no desempate (idade)
  email            String
  cpf              String
  situacao         String       @default("ATIVO") // só ATIVO entra no ranking
  classId          String       @map("class_id") @db.Uuid
  apresentacaoEc   DateTime?    @map("apresentacao_ec")
  apresentacaoMx   DateTime?    @map("apresentacao_mx")
  attendances      Attendance[]
  class            Class        @relation(fields: [classId], references: [id])
  loja             Loja         @relation(fields: [lojaId], references: [id])
  tenant           Tenant       @relation(fields: [tenantId], references: [id], onDelete: Cascade)

  @@unique([tenantId, cpf])
  @@index([tenantId, nomeCompleto])
  @@index([situacao])
  @@index([lojaId])
  @@index([classId])
  @@map("member")
}

model Meeting {
  id          String       @id @default(uuid())
  tenantId    String
  lojaId      String?      // null = sessão do tenant inteiro
  dataSessao  DateTime
  tipo        String
  titulo      String?
  attendances Attendance[]
  loja        Loja?        @relation(fields: [lojaId], references: [id])
  tenant      Tenant       @relation(fields: [tenantId], references: [id], onDelete: Cascade)

  @@index([tenantId])
  @@index([lojaId])
  @@index([dataSessao])
  @@map("meeting")
}

model Attendance {
  id         String   @id @default(uuid())
  tenantId   String
  meetingId  String
  memberId   String
  status     String   // "PRESENTE" | "FALTA" | "JUSTIFICADA"
  observacoes String?
  createdAt  DateTime @default(now())
  updatedAt  DateTime @updatedAt
  meeting    Meeting  @relation(fields: [meetingId], references: [id], onDelete: Cascade)
  member     Member   @relation(fields: [memberId], references: [id], onDelete: Cascade)
  tenant     Tenant   @relation(fields: [tenantId], references: [id], onDelete: Cascade)

  @@unique([meetingId, memberId]) // 1 status por membro por sessão
  @@index([tenantId])
  @@index([meetingId])
  @@index([memberId])
  @@map("attendance")
}

model Class {
  abbreviation String   @unique @db.VarChar(4) // "MX", "EC", ...
  name         String   @db.VarChar(70)
  id           String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  members      Member[]

  @@map("class")
}

model Loja {
  id        String    @id @default(uuid())
  tenantId  String
  lojaMX    String
  numero    Int?
  situacao  String    @default("ATIVA")
  meetings  Meeting[]
  members   Member[]
  tenant    Tenant    @relation(fields: [tenantId], references: [id], onDelete: Cascade)

  @@index([tenantId])
  @@map("loja")
}
```

**Pontos-chave de portabilidade:**
- `@@unique([meetingId, memberId])` garante idempotência do status.
- Índices em `dataSessao`, `lojaId`, `classId`, `situacao` sustentam as queries do ranking.
- `Class.abbreviation` é o filtro de classe (`classes=MX` ou `classes=EC` na URL).

---

## 6. Arquitetura e fluxo de dados

```
/ranking (page.tsx — Server Component)
  ├── guards: getCurrentUser, canAccessPresence, presencaFixedLojaScopeOnly
  ├── resolve lojaFilter (valida UUID + pertencimento ao tenant)
  ├── MEMBER → busca linkedMemberId por email (case-insensitive)
  ├── counts: membros ATIVOS EC / MX no escopo  ──→ KPIs
  └── render <RankingClient>
        ├── estado local: selectedClass ("MX" | "EC")
        ├── período: startOfWindow = 1/jan/(ano−2) … hoje (formato ISO yyyy-mm-dd)
        └── <AttendanceFrequencyTable
              lojaId dataInicio dataFim classes=[selectedClass]
              apresentacaoMode={selectedClass} embedded emeraldTone />
                └── fetch GET /api/presenca/frequencia?...  (Client-side)
                      ├── resolvePresencaLojaId (escopo por papel)
                      ├── meetings: only canMarkAttendance(dataSessao)
                      ├── members: ATIVO + loja + classe
                      ├── attendances: dos meetingIds
                      └── memberStats: totalPresent/totalRecorded/percentage
                └── rankingRows: sort composto (§8.2) no useMemo
```

**Arquivos (referência no repo):**

| Arquivo | Papel |
|---|---|
| `app/src/app/ranking/page.tsx` | Server Component: auth, escopo, KPIs |
| `app/src/app/ranking/page-client.tsx` | Client: filtros classe/loja, KPIs, embute a tabela |
| `app/src/components/presenca/AttendanceFrequencyTable.tsx` | Matriz de frequência + ranking + paginação + sort |
| `app/src/app/api/presenca/frequencia/route.ts` | API de dados do ranking |
| `app/src/app/api/presenca/relatorios/route.ts` | Relatórios, incl. `tipo=ranking` (assiduidade) |
| `app/src/lib/session-rules.ts` | `canMarkAttendance` — regra "sessão já ocorreu" |
| `app/src/lib/presenca-scope.ts` | `resolvePresencaLojaId` — escopo loja por papel |
| `app/src/lib/roles.ts` | `canAccessPresence`, `presencaFixedLojaScopeOnly`, `presencaCanSelectLojaFilter` |
| `app/src/components/ui/kpi-card.tsx` | Card de KPI |

---

## 7. RBAC e escopo multi-tenant

### 7.1 Funções de papel (`src/lib/roles.ts`)

```ts
export function canAccessPresence(role: RoleInput) {
  return (
    isSaasAdmin(role) ||
    isLojaAdmin(role) ||
    isSecretaria(role) ||
    isTesouraria(role) ||
    isPotAdmin(role) ||
    role === "SYS_ADMIN" ||
    role === "MEMBER"
  );
}

/** Presença: perfil fica só na própria loja (sem combo "todas as lojas"). */
export function presencaFixedLojaScopeOnly(role: RoleInput): boolean {
  if (!role) return false;
  if (role === "MEMBER") return true;
  return isSecretaria(role) || isTesouraria(role) || isLojaAdmin(role);
}

/** Pode usar o filtro por loja ou "todas" na página /presenca. */
export function presencaCanSelectLojaFilter(role: RoleInput): boolean {
  return canAccessPresence(role) && !presencaFixedLojaScopeOnly(role);
}
```

Matriz resultante:

| Papel | Acessa /ranking | Escopo loja | Vê |
|---|---|---|---|
| MEMBER | ✔ | Fixa na própria loja | Só o próprio membro |
| Secretaria / Tesouraria / Admin loja | ✔ | Fixa na própria loja | Toda a loja |
| SYS_ADMIN / GRANDE_* (globais) | ✔ | Filtro opcional "todas" | Tenant inteiro |
| Demais papéis | ✘ redirect `/` | — | — |

### 7.2 Resolução da loja efetiva (`src/lib/presenca-scope.ts`)

```ts
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export async function resolvePresencaLojaId(params: {
  tenantId: string;
  role: string;
  userLojaId: string | null | undefined;
  queryLojaId: string | null;
}): Promise<{ lojaId: string | undefined; missingUserLoja: boolean }> {
  const { tenantId, role, userLojaId, queryLojaId } = params;

  if (presencaFixedLojaScopeOnly(role)) {
    if (!userLojaId) return { lojaId: undefined, missingUserLoja: true };
    return { lojaId: userLojaId, missingUserLoja: false };
  }

  const raw = queryLojaId?.trim() ?? "";
  if (!raw || raw === "all" || !UUID_RE.test(raw)) {
    return { lojaId: undefined, missingUserLoja: false };
  }

  const isGlobalScope =
    role === "SYS_ADMIN" || role === "GRANDE_CHANCELER" ||
    role === "GRANDE_TESOUREIRO" || role === "GRANDE_PRIOR";

  const ok = await prisma.loja.findFirst({
    where: isGlobalScope ? { id: raw } : { id: raw, tenantId },
    select: { id: true },
  });

  return { lojaId: ok?.id, missingUserLoja: false };
}
```

> **Nota de portabilidade:** ao adaptar, troque os literais de papel pelos do seu sistema e mantenha o padrão: **fixo → valida existência; opcional → valida formato (UUID) + pertencimento ao tenant**. Isso evita IDOR via `?lojaId=`.

### 7.3 Vínculo MEMBER → Member (na página)

```ts
let linkedMemberId: string | undefined;
if (user.role === "MEMBER") {
  const selfMember = await prisma.member.findFirst({
    where: {
      tenantId: user.tenantId,
      email: { equals: user.email, mode: "insensitive" },
    },
    select: { id: true },
  });
  linkedMemberId = selfMember?.id;
}
```

---

## 8. Especificação das regras de cálculo

### 8.1 Estatísticas de frequência (API)

Para cada membro, sobre o conjunto de sessões realizadas no período/escopo:

```
totalPresent  = nº de Attendance com status === "PRESENTE"
totalRecorded = totalMeetings (todas as sessões do período — mesmo sem registro)
percentage    = round((totalPresent / totalMeetings) * 100)   // 0 se totalMeetings = 0
```

- `FALTA` e `JUSTIFICADA` **não** somam presença.
- Ausência de registro (célula vazia) conta como não-presente no denominador.

### 8.2 Ordenação do ranking de apresentação (cliente)

Constantes:
- Limiar de tempo: `threshold = apresentacaoMode === "EC" ? 12 : 18` meses.
- Presença válida: `presencas >= 4`.
- `mediaDesempate = idade` (anos completos entre `dataNascimento` e hoje; 0 se inválida).
- `meetsTime = tempoApresentacaoMeses >= threshold`.

Comparador (ordem de prioridade, todos decidem antes do próximo):

```
1. meetsTime            → quem cumpriu o tempo vem primeiro
2. tempoApresentacaoMeses → maior primeiro (mais antigo na função)
3. presencaValida       → quem tem ≥4 presenças vem primeiro
4. mediaDesempate (idade) → maior primeiro
5. originalIndex        → ordem alfabética do nome (estável)
```

### 8.3 Utilitários de data (meses/anos completos)

```ts
const monthsBetween = (start?: string | null | Date, end = new Date()) => {
  if (!start) return 0;
  const startDate = start instanceof Date ? start : new Date(start);
  if (Number.isNaN(startDate.getTime())) return 0;
  let months = (end.getFullYear() - startDate.getFullYear()) * 12;
  months += end.getMonth() - startDate.getMonth();
  if (end.getDate() < startDate.getDate()) months--; // mês incompleto
  return Math.max(months, 0);
};

const yearsBetween = (start?: string | null | Date, end = new Date()) => {
  if (!start) return 0;
  const startDate = start instanceof Date ? start : new Date(start);
  if (Number.isNaN(startDate.getTime())) return 0;
  let years = end.getFullYear() - startDate.getFullYear();
  if (
    end.getMonth() < startDate.getMonth() ||
    (end.getMonth() === startDate.getMonth() && end.getDate() < startDate.getDate())
  ) years--;
  return Math.max(years, 0);
};
```

### 8.4 Regra "sessão já ocorreu" (`src/lib/session-rules.ts`)

```ts
function normalizeDateToStartOfDay(date: Date): Date {
  const normalized = new Date(date);
  const saoPauloOffset = -3 * 60;            // minutos (UTC-3)
  const localOffset = normalized.getTimezoneOffset();
  const diff = saoPauloOffset - localOffset;
  normalized.setHours(0, 0, 0, 0);
  normalized.setMinutes(normalized.getMinutes() + diff);
  return normalized;
}

export function canMarkAttendance(sessionDate: Date | string, now?: Date): boolean {
  const sessaoDate = typeof sessionDate === "string" ? new Date(sessionDate) : sessionDate;
  const currentDate = now ? new Date(now) : new Date();
  const sessaoNormalized = normalizeDateToStartOfDay(sessaoDate);
  const todayNormalized = normalizeDateToStartOfDay(currentDate);
  return sessaoNormalized.getTime() <= todayNormalized.getTime();
}
```

> Sessões futuras ficam de fora da frequência/ranking mesmo que já cadastradas.

### 8.5 Ranking de assiduidade (relatórios `tipo=ranking`)

```
por membro: total = nº de Attendance no período
            percentualPresenca = round(presentes / total * 100)   // 0 se total = 0
ordem:      percentualPresenca DESC
```

> Diferença sutil vs §8.1: aqui o denominador é o nº de **registros** do membro (não o total de sessões do período).

---

## 9. Contratos de API

### 9.1 `GET /api/presenca/frequencia`

Query: `lojaId?` (uuid|"all"), `dataInicio?` (yyyy-mm-dd), `dataFim?`, `classes?` ("MX,EC" — maiúsculas, trim).

Resposta 200:

```jsonc
{
  "meetings":    [{ "id", "dataSessao", "tipo", "titulo" }],               // ordem dataSessao asc, só realizadas
  "members":     [{ "id", "nomeCompleto", "apresentacaoMx", "apresentacaoEc",
                     "dataNascimento", "class": { "abbreviation", "name" } }],
  "attendances": [{ "memberId", "meetingId", "status" }],
  "memberStats": [{ "memberId", "memberName", "memberClass",
                     "totalPresent", "totalRecorded", "percentage" }]
}
```

Erros: 401 não autenticado; 403 sem permissão ou usuário sem loja vinculada; 404 usuário não encontrado; 500 erro interno.

### 9.2 `GET /api/presenca/relatorios?tipo=ranking`

Resposta 200: `{ "ranking": [{ "member": {…}, "total", "presentes", "faltas", "justificadas", "percentualPresenca" }] }` ordenado por `percentualPresenca` desc.

---

## 10. Especificação de tela (`/ranking`)

1. **Header** — breadcrumb "Presença", título "Ranking", descrição contextual por escopo; botão-link "Sessões" → `/presenca`.
2. **KPIs** (grid 3 colunas) — Total no ranking (`ec+mx`), Escudeiros noviços (EC), Mestres de mesa (MX).
3. **Painel de filtros** (card gradiente com glows radiais):
   - Texto do período: `dataInicio` a `dataFim` (últimos 24 meses).
   - Select "Loja" (só quando `canSelectLoja`): opções "Todas as lojas" + lojas ordenadas por `lojaMX asc, numero asc`; change → `router.push(/ranking?lojaId=…)`.
   - Radios de classe: MX ("Responsáveis pela direção das sessões de Mesa.") / EC ("Escudeiros noviços com presença registrada nas caravanas.").
4. **Tabela embutida** (`AttendanceFrequencyTable`, `embedded emeraldTone`):
   - Cabeçalho sticky verde-esmeralda; colunas fixas sticky: `RK` (60px), `Nome` (220px), `Apresentação` (180px, ordenável).
   - Colunas dinâmicas por sessão (dd/mm/aa, `title` com tipo+título+data).
   - Ícones de status por célula (✓ verde / ✗ vermelho / ⚠ âmbar / — cinza).
   - `%` colorida por faixa; `Total` como `presentes/registradas`.
   - Rodapé: paginação 20/página com RK global; legenda de status.
   - Vazios distintos: "Nenhum membro ativo encontrado." vs "Nenhuma sessão encontrada no período selecionado."; loading spinner; error banner vermelho.

---

## 11. Sprints passo a passo (portáveis)

> Ordem recomendada. Cada sprint termina com critérios de aceite verificáveis. Código completo abaixo; ajuste imports/alias (`@/` → `src/`) e tokens de tema ao portar.

### Sprint 0 — Setup do projeto-alvo

**Tarefas**
1. Next.js App Router + TS strict + Tailwind v4 + Prisma.
2. Alias `@/` → `src/*` no `tsconfig.json`.
3. Auth de sessão existente exposta como `getCurrentUser()` (server) e `authenticateRequest(req)` (API).

**Aceite** — app sobe, login funciona, `prisma generate` ok.

---

### Sprint 1 — Modelo de dados + seed

**Tarefas**
1. Copiar os models do §5 para `prisma/schema.prisma`.
2. `npx prisma migrate dev --name ranking-core`.
3. Seed mínimo: 1 tenant, 1–2 lojas, classes `MX`/`EC`, ~10 membros ATIVOS (com `apresentacaoMx`/`apresentacaoEc`/`dataNascimento` variados), ~8 sessões passadas + 1 futura, attendances misturando os 3 status.

**Aceite** — `db:reset && db:seed` idempotente; sessão futura existe para validar RF-11.

---

### Sprint 2 — Regras de negócio puras (`src/lib`)

**2.1 `src/lib/session-rules.ts`** — copiar §8.4 inteiro.

**2.2 `src/lib/roles.ts`** — implementar `canAccessPresence`, `presencaFixedLojaScopeOnly`, `presencaCanSelectLojaFilter` (§7.1), adaptando `isSaasAdmin/isLojaAdmin/...` aos seus papéis.

**2.3 `src/lib/presenca-scope.ts`** — copiar §7.2.

**Estrutura das funções:**

```ts
// session-rules.ts
normalizeDateToStartOfDay(date: Date): Date            // privado
canMarkAttendance(sessionDate: Date|string, now?: Date): boolean
getAttendanceBlockedMessage(): string
getAttendanceBlockedCode(): string

// presenca-scope.ts
resolvePresencaLojaId(p): Promise<{ lojaId?: string; missingUserLoja: boolean }>
getPresenceLinkedMemberId(tenantId, role, email): Promise<string|undefined>

// roles.ts
canAccessPresence(role): boolean
presencaFixedLojaScopeOnly(role): boolean
presencaCanSelectLojaFilter(role): boolean
```

**Aceite** — `canMarkAttendance(new Date()) === true`; `canMarkAttendance(amanhã) === false`; lint ok.

---

### Sprint 3 — API `/api/presenca/frequencia`

Criar `src/app/api/presenca/frequencia/route.ts`:

```ts
import { NextRequest, NextResponse } from "next/server";
import { authenticateRequest, getUserFromPayload } from "@/lib/api-auth";
import prisma from "@/lib/prisma";
import { Prisma } from "@prisma/client";
import { canMarkAttendance } from "@/lib/session-rules";
import { canAccessPresence } from "@/lib/roles";
import { getPresenceLinkedMemberId, resolvePresencaLojaId } from "@/lib/presenca-scope";
import { logger } from "@/lib/logger";

export async function GET(req: NextRequest) {
  const auth = await authenticateRequest(req);
  if (!auth) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  if (!canAccessPresence(auth.role)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  try {
    const user = await getUserFromPayload(auth);
    if (!user) return NextResponse.json({ error: "Usuario nao encontrado" }, { status: 404 });

    const { searchParams } = new URL(req.url);
    const requestedLojaId = searchParams.get("lojaId");
    const dataInicio = searchParams.get("dataInicio");
    const dataFim = searchParams.get("dataFim");
    const classesParam = searchParams.get("classes");

    const { lojaId, missingUserLoja } = await resolvePresencaLojaId({
      tenantId: auth.tenantId, role: auth.role,
      userLojaId: user.lojaId, queryLojaId: requestedLojaId,
    });
    if (missingUserLoja) {
      return NextResponse.json({ error: "Usuario sem loja vinculada" }, { status: 403 });
    }

    const linkedMemberId = await getPresenceLinkedMemberId(auth.tenantId, auth.role, auth.email);
    if (auth.role === "MEMBER" && !linkedMemberId) {
      return NextResponse.json({ meetings: [], members: [], attendances: [], memberStats: [] });
    }

    const classFilters =
      classesParam?.split(",").map((v) => v.trim().toUpperCase()).filter((v) => v.length > 0) ?? [];

    const meetingWhere: Prisma.MeetingWhereInput = {
      tenantId: auth.tenantId,
      ...(lojaId ? { lojaId } : {}),
    };
    if (dataInicio || dataFim) {
      meetingWhere.dataSessao = {};
      if (dataInicio) meetingWhere.dataSessao.gte = new Date(dataInicio);
      if (dataFim) {
        const endOfDay = new Date(dataFim);
        endOfDay.setHours(23, 59, 59, 999);
        meetingWhere.dataSessao.lte = endOfDay;
      }
    }

    const allMeetings = await prisma.meeting.findMany({
      where: meetingWhere,
      select: { id: true, dataSessao: true, tipo: true, titulo: true },
      orderBy: { dataSessao: "asc" },
    });

    // Só sessões já realizadas contam na frequência
    const meetings = allMeetings.filter((m) => canMarkAttendance(m.dataSessao));

    const memberWhere: Prisma.MemberWhereInput = {
      tenantId: auth.tenantId,
      situacao: "ATIVO",
      ...(lojaId ? { lojaId } : {}),
      ...(linkedMemberId ? { id: linkedMemberId } : {}),
    };
    if (classFilters.length > 0) {
      memberWhere.class = { abbreviation: { in: classFilters } };
    }

    const members = await prisma.member.findMany({
      where: memberWhere,
      select: {
        id: true, nomeCompleto: true,
        apresentacaoMx: true, dataNascimento: true, apresentacaoEc: true,
        class: { select: { abbreviation: true, name: true } },
      },
      orderBy: { nomeCompleto: "asc" },
    });

    const meetingIds = meetings.map((m) => m.id);
    const attendances = await prisma.attendance.findMany({
      where: {
        tenantId: auth.tenantId,
        meetingId: { in: meetingIds },
        ...(linkedMemberId ? { memberId: linkedMemberId } : {}),
      },
      select: { meetingId: true, memberId: true, status: true },
    });

    // Mapa memberId_meetingId → status
    const attendanceMap = new Map<string, string>();
    attendances.forEach((att) => attendanceMap.set(`${att.memberId}_${att.meetingId}`, att.status));

    const totalMeetings = meetings.length;
    const memberStats = members.map((member) => {
      let totalPresent = 0;
      meetings.forEach((meeting) => {
        if (attendanceMap.get(`${member.id}_${meeting.id}`) === "PRESENTE") totalPresent++;
      });
      const percentage = totalMeetings > 0
        ? Math.round((totalPresent / totalMeetings) * 100) : 0;
      return {
        memberId: member.id, memberName: member.nomeCompleto,
        memberClass: member.class?.abbreviation ?? null,
        totalPresent, totalRecorded: totalMeetings, percentage,
      };
    });

    return NextResponse.json({
      meetings, members,
      attendances: Array.from(attendanceMap.entries()).map(([key, status]) => {
        const [memberId, meetingId] = key.split("_");
        return { memberId, meetingId, status };
      }),
      memberStats,
    });
  } catch (error) {
    logger.error("Error fetching attendance frequency:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
```

**Aceite** — curl autenticado com `classes=MX` retorna só membros MX; sessão futura não aparece em `meetings`; `%` bate com contagem manual.

---

### Sprint 4 — API `/api/presenca/relatorios` (tipo ranking)

Criar `src/app/api/presenca/relatorios/route.ts` — handlers `por-periodo`, `por-membro` e `ranking`. O bloco do ranking (§8.5):

```ts
if (tipo === "ranking") {
  const members = await prisma.member.findMany({
    where: {
      tenantId: auth.tenantId,
      situacao: "ATIVO",
      ...(resolvedLoja ? { lojaId: resolvedLoja } : {}),
      ...(linkedMemberId ? { id: linkedMemberId } : {}),
    },
    select: {
      id: true, nomeCompleto: true,
      class: { select: { abbreviation: true, name: true } },
    },
  });

  const ranking = await Promise.all(
    members.map(async (member) => {
      const attendances = await prisma.attendance.findMany({
        where: {
          memberId: member.id,
          tenantId: auth.tenantId,
          meeting: {
            tenantId: auth.tenantId,
            ...(resolvedLoja ? { lojaId: resolvedLoja } : {}),
            ...meetingDateFilter,
          },
        },
      });

      const total = attendances.length;
      const presentes = attendances.filter((a) => a.status === "PRESENTE").length;
      const faltas = attendances.filter((a) => a.status === "FALTA").length;
      const justificadas = attendances.filter((a) => a.status === "JUSTIFICADA").length;

      return {
        member, total, presentes, faltas, justificadas,
        percentualPresenca: total > 0 ? Math.round((presentes / total) * 100) : 0,
      };
    })
  );

  ranking.sort((a, b) => b.percentualPresenca - a.percentualPresenca);
  return NextResponse.json({ ranking });
}
```

O restante do arquivo (guards, `meetingDateFilter`, `por-periodo`, `por-membro`) segue o código-fonte completo em `app/src/app/api/presenca/relatorios/route.ts` (repo SALDARER).

**Aceite** — `?tipo=ranking` ordena por % desc; `tipo` ausente → 400.

---

### Sprint 5 — Tela `/ranking` (Server Component)

Criar `src/app/ranking/page.tsx` (código íntegro em §"Arquivos", resumo da estrutura):

```ts
export default async function RankingPage({
  searchParams,
}: { searchParams: Promise<{ lojaId?: string }> }) {
  // 1. auth + guards (redirect /login, /)
  // 2. fixedLojaScope / canSelectLoja por papel
  // 3. valida ?lojaId contra o tenant (prisma.loja.findFirst)
  // 4. MEMBER → linkedMemberId por email insensitive
  // 5. memberScope = { tenantId, situacao: "ATIVO", lojaId?, id? }
  // 6. lojaOptions (se canSelectLoja) ordenadas lojaMX asc, numero asc
  // 7. counts EC/MX (Promise.all)
  // 8. <RankingClient frequencyLojaId memberRankingCounts rankingUi />
}
```

Código real:

```ts
import { redirect } from "next/navigation";
import { Prisma } from "@prisma/client";
import prisma from "@/lib/prisma";
import RankingClient from "./page-client";
import { getCurrentUser } from "@/lib/server-auth";
import {
  canAccessPresence,
  presencaCanSelectLojaFilter,
  presencaFixedLojaScopeOnly,
} from "@/lib/roles";

export default async function RankingPage({
  searchParams,
}: {
  searchParams: Promise<{ lojaId?: string }>;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (!canAccessPresence(user.role)) redirect("/");

  const fixedLojaScope = presencaFixedLojaScopeOnly(user.role);
  const canSelectLoja = presencaCanSelectLojaFilter(user.role);
  if (fixedLojaScope && !user.lojaId) redirect("/");

  const sp = await searchParams;
  const rawLojaId = sp.lojaId?.trim();

  let lojaFilter: string | undefined;
  if (fixedLojaScope) {
    lojaFilter = user.lojaId ?? undefined;
  } else if (canSelectLoja && rawLojaId && rawLojaId !== "all") {
    const ok = await prisma.loja.findFirst({
      where: { id: rawLojaId, tenantId: user.tenantId },
      select: { id: true },
    });
    lojaFilter = ok?.id;
  }

  let linkedMemberId: string | undefined;
  if (user.role === "MEMBER") {
    const selfMember = await prisma.member.findFirst({
      where: { tenantId: user.tenantId, email: { equals: user.email, mode: "insensitive" } },
      select: { id: true },
    });
    linkedMemberId = selfMember?.id;
  }

  const memberScope: Prisma.MemberWhereInput = {
    tenantId: user.tenantId,
    situacao: "ATIVO",
    ...(lojaFilter ? { lojaId: lojaFilter } : {}),
    ...(linkedMemberId ? { id: linkedMemberId } : {}),
  };

  const lojaOptions = canSelectLoja
    ? await prisma.loja.findMany({
        where: { tenantId: user.tenantId },
        select: { id: true, lojaMX: true, numero: true },
        orderBy: [{ lojaMX: "asc" }, { numero: "asc" }],
      })
    : [];

  const selectedLojaId =
    !canSelectLoja || !rawLojaId || rawLojaId === "all" || !lojaFilter ? "all" : lojaFilter;

  const [ecMembersTotal, mxMembersTotal] = await Promise.all([
    prisma.member.count({ where: { ...memberScope, class: { abbreviation: "EC" } } }),
    prisma.member.count({ where: { ...memberScope, class: { abbreviation: "MX" } } }),
  ]);

  return (
    <RankingClient
      frequencyLojaId={lojaFilter}
      memberRankingCounts={{ ec: ecMembersTotal, mx: mxMembersTotal }}
      rankingUi={{ fixedLojaScope, canSelectLoja, lojaOptions, selectedLojaId }}
    />
  );
}
```

**Aceite** — sem login redireciona; MEMBER vê 1 linha; `?lojaId` inválido cai em "todas".

---

### Sprint 6 — Client Component (`src/app/ranking/page-client.tsx`)

Estrutura:

```tsx
"use client";
Props: { frequencyLojaId?, memberRankingCounts: { ec, mx },
         rankingUi?: { fixedLojaScope, canSelectLoja, lojaOptions, selectedLojaId } }

const now = new Date();
const startOfWindow = new Date(now.getFullYear() - 2, 0, 1);  // 1º jan, ano-2 (24 meses)
formatDateForFilter = (d) => d.toISOString().split("T")[0]

estado: selectedClass: "MX" | "EC"  (default "MX")

UI:
  Header (breadcrumb Presença / título Ranking / descrição por escopo / link Sessões)
  KPIs (KpiCard ×3: total, EC, MX)
  Painel filtros:
    - select Loja (se canSelectLoja) → router.push("/ranking?lojaId=…")
    - radios MX / EC (rankingOptions)
  <AttendanceFrequencyTable lojaId={frequencyLojaId} dataInicio dataFim
     classes={[selectedClass]} apresentacaoMode={selectedClass} embedded emeraldTone />
```

`rankingOptions`:

```ts
const rankingOptions = [
  { value: "MX", label: "Mestre de Mesa (MX)",
    description: "Responsáveis pela direção das sessões de Mesa." },
  { value: "EC", label: "Escudeiro Noviço (EC)",
    description: "Escudeiros noviços com presença registrada nas caravanas." },
] as const;
```

**Aceite** — trocar classe refaz o fetch da tabela; select de loja muda a URL e recarrega o server component.

---

### Sprint 7 — `AttendanceFrequencyTable` (componente núcleo)

Arquivo: `src/components/presenca/AttendanceFrequencyTable.tsx`. Código completo no repo (826 linhas); abaixo a anatomia essencial para portar:

```tsx
"use client";
Props: { lojaId?, dataInicio?, dataFim?, classes?: string[],
         apresentacaoMode?: "MX" | "EC", embedded?: boolean, emeraldTone?: boolean }

Tipos internos:
  Meeting / Member / AttendanceRecord / MemberStats / FrequencyData
  SortField = "name" | "total" | "percentage" | "presentation"
  SortDirection = "asc" | "desc"
Constante: FREQUENCY_MEMBERS_PAGE_SIZE = 20

Estados: data, loading, error, sortField, sortDirection, memberPage

useEffect #1: ao trocar apresentacaoMode → sortField="presentation", dir="desc"
              (sem modo → "name"/"asc")
useEffect #2: reset memberPage=1 quando filtros/sort mudam
useEffect #3: fetch /api/presenca/frequencia (classes normalizadas: trim+upper),
              deps: [lojaId, dataInicio, dataFim, classes?.join(",")]

useMemo attendanceMap: Map<`${memberId}_${meetingId}`, status>

helpers de data: formatDate (dd/mm/aa), formatPresentationDate (dd/mm/aaaa),
                 monthsBetween, yearsBetween  (§8.3)

useMemo rankingRows (núcleo do ranking — §8.2):
  threshold = apresentacaoMode === "EC" ? 12 : 18
  por membro:
    presentationRaw   = EC ? apresentacaoEc : apresentacaoMx
    tempoApresentacaoMeses = monthsBetween(presentationRaw, now)
    presencas         = stats?.totalPresent ?? 0
    presencaValida    = presencas >= 4
    mediaDesempate    = idade (yearsBetween(dataNascimento))
    meetsTime         = tempo >= threshold
  sort comparador encadeado (5 níveis, §8.2)

useMemo generalRows / sortedGeneralRows (modo sem apresentacaoMode):
  sort por percentage | total | name/presentation (localeCompare pt-BR)

useMemo rankingSortedRows: re-sort de rankingRows quando usuário
  clica em % ou total (name/presentation mantêm a ordem do ranking)

handleSort(field): toggle asc/desc; SortIcon (ArrowUpDown/Up/Down)

paginação: slice de tableRows por página de 20; rk = (page-1)*20 + index + 1

render: loading / error / empty-members / empty-meetings / tabela:
  thead sticky (RK 60px | Nome 220px | Apresentação 180px | …meetings | % | Total)
  tbody: células de status por sessão via attendanceMap; % colorida (≥75/≥50);
         total presentes/registradas
  rodapé: paginação + legenda (Presente/Falta/Justificada/Sem registro)
```

Comparador do ranking (cópia fiel):

```ts
.sort((a, b) => {
  if (a.meetsTime !== b.meetsTime) return b.meetsTime ? 1 : -1;
  if (b.tempoApresentacaoMeses !== a.tempoApresentacaoMeses)
    return (b.tempoApresentacaoMeses ?? 0) - (a.tempoApresentacaoMeses ?? 0);
  if ((a.presencaValida ? 1 : 0) !== (b.presencaValida ? 1 : 0))
    return (b.presencaValida ? 1 : 0) - (a.presencaValida ? 1 : 0);
  if ((b.mediaDesempate ?? 0) !== (a.mediaDesempate ?? 0))
    return (b.mediaDesempate ?? 0) - (a.mediaDesempate ?? 0);
  return a.originalIndex - b.originalIndex;
});
```

**Aceite** — membro com 20 meses de apresentação e 5 presenças fica acima de membro com 10 meses e 10 presenças (meetsTime domina); RK continua global ao paginar.

---

### Sprint 8 — Navegação, tema e polimento

1. Item de nav `Ranking → /ranking` (ícone `Trophy`), atalho `g r` no keyboard-shortcuts.
2. Bloquear rota para perfis sem acesso no middleware/proxy (lista `CANDIDATO_BLOCKED_PREFIXES` inclui `/ranking`).
3. Tokens `obs-*` no `globals.css` (ou substituir pela paleta do app-alvo); variante `emeraldTone` só na Ranking.
4. `KpiCard` (`variant="observatory"`, ícones `Trophy`/`Users`).

**Aceite** — navegação e atalho funcionam; candidato/sem papel é bloqueado.

---

### Sprint 9 — Verificação E2E

1. `npm run db:reset && npm run db:seed` (dados determinísticos).
2. Playwright `tests/ranking.spec.ts`:
   - login como admin global → vê KPIs, alterna MX/EC, pagina;
   - login como MEMBER → vê apenas a própria linha;
   - sessão futura não aparece como coluna;
   - ordenação esperada para fixtures conhecidos (caso meetsTime × presencaValida).
3. `npm run lint` + `npm run build`.

**Aceite** — specs verdes; build limpo.

---

## 12. Checklist de adaptação para outra aplicação

- [ ] Renomear papéis em `roles.ts` para o RBAC-alvo.
- [ ] `tenantId` obrigatório em todas as queries (ou remover se single-tenant).
- [ ] Ajustar `normalizeDateToStartOfDay` se o fuso-alvo ≠ UTC-3.
- [ ] Substituir `lucide-react`, `KpiCard`, tokens `obs-*`/emerald pelos equivalentes do design system alvo.
- [ ] Confirmar unicidade `@@unique([meetingId, memberId])` e índices antes de popular.
- [ ] Parameterizar `threshold` (12/18) e `presencaValida >= 4` como constantes/config se o domínio mudar.
- [ ] Manter o padrão de guardas: 401 → 403 (papel) → 403 (sem loja) → 404 (usuário).

## 13. Riscos e decisões registradas

| Decisão | Motivo |
|---|---|
| Denominador do % = total de sessões do período (não só registradas) | Ausência de registro é tratada como não-presente. |
| Sessões futuras excluídas server-side | Impede inflar denominador com sessões não realizadas. |
| Ranking calculado no cliente a partir de `memberStats` | Mantém a API genérica (reuso na página `/presenca`) e o sort responsivo. |
| `relatorios?tipo=ranking` usa outro denominador (registros do membro) | Legado dos relatórios; documentado em §8.5 para evitar confusão. |
| `getPresenceLinkedMemberId` retorna `undefined` (MEMBER vê calendário da loja) | Restrição de edição é feita por permissão de escrita, não de leitura; a página `/ranking` aplica o vínculo via `linkedMemberId` próprio. |
