# PRD — SAL DA BRITÂNEA CRM

> **Documento master de produto.** Visão, escopo, modelo de dados, regras de negócio e requisitos por módulo.
> Documentação técnica/arquitetura: [`README.md`](README.md) (mesma pasta).
> Estado: reflete o sistema em **outubro/2026**, já no banco único **`saldabritanea`**.

## 1. Visão do produto

**Sal da Britânea CRM** é o sistema de gestão de uma organização maçônica — hoje operando a Grande Loja de Mestres Maçons da Marca (GLMMMRJ/RJ). Ele unifica, num único painel web, a gestão de **membros, lojas, potências, recepção** e as operações de **filiados e congresso**, substituindo dois sistemas:

| Antes | Hoje |
|-------|------|
| GPRB CRM (sistema herdado, desenho Prisma) — gestão de membros/lojas | **Unificado neste sistema** |
| CRM de vendas (fork Django esferasda) — funil, automações, campanhas | **Unificado neste sistema** |
| Dois bancos separados (`saldogprb` + `esferasda_crm`) | **Um único banco: `saldabritanea`** |

O sistema é um **fork multi-tenant de CRM de vendas adaptado ao contexto maçônico**: a camada "comercial" (funil, campanhas, automações) reaproveita o motor herdado do CRM; a camada de membros/lojas/potências (modelo GPRB) é a fonte da verdade cadastral.

## 2. Personas

| Papel | Quem é | Uso principal |
|-------|--------|---------------|
| **Grão-Mestre / direção da Potência** | Liderança da organização | Dashboard, visão consolidada de membros e lojas, decisões |
| **Presidente de loja** | Responsável por uma loja | Membros da sua loja, recepção, agenda |
| **Recepção / secretaria** | Operador do dia a dia | Cadastro e edição de membros, check-in, inclui/altera lojas do membro (N:N) |
| **Equipe administrativa** | Filiação, tesouraria, congresso | Situação de membros (ATIVO/INATIVO), financeiro, inscrições |
| **admin_saas** | Operador da plataforma | Acesso a todos os tenants (uso interno) |

Papéis técnicos: `admin_saas`, `admin_company`, `operacional`, `viewer` (somente leitura).

## 3. Modelo de dados (referência)

Fonte da verdade técnica: banco `saldabritanea` (49 tabelas — 13 do modelo GPRB + 36 do núcleo Django).

### 3.1 Modelo cadastral GPRB

```
tenant ──< user                    (usuários de login, bcrypt)
potencia (origem maçônica) ──< member/candidato
rito ──< member
prefeitura  (→ exibida como "Potência" na tela) ──< loja
loja  >──< member                  via member_loja (N:N com dataInclusao)
member ──< payment ──< payment_period / payment_status
loja ──< meeting ──< attendance ──< member
```

**Regras estruturantes:**

1. **N:N membro ↔ lojas** (`member_loja`, PK composta `memberId`+`lojaId`, coluna `dataInclusao`). A **primeira** loja do membro é a **principal** e é espelhada em `member."lojaId"`, que é *nullable* — um membro pode existir sem loja.
2. **Sem classes.** `member.class_id`, a tabela `class` (MX/EN/CBCS) e todo conceito de "grau" foram **eliminados do produto**. A situação do membro é binária: `ATIVO` / `INATIVO`.
3. **Sem coluna de região.** `prefeitura.regiao` foi eliminada — a Potência é editável só por nome, sigla, grão-mestre, contatos e endereço.
4. **`prefeitura` = Potência** (entidade organizacional das telas). **`potencia`** = origem maçônica (GOB, COMAB, CSMB, GLMMMRJ…) — conceito distinto, ligado a `member`/`candidato`.
5. Colunas de auditoria padrão: `createdAt` / `updatedAt`.

### 3.2 Núcleo Django (motor comercial herdado)

`usuarios`,`tenants`,`contatos`+`tags`,`negocios`+`etapas_funil`,`tarefas`,`automacoes`(+`_execucoes`/`_passos`),`campanhas`,`emails_enviados`+`modelos_email`,`chamadas`+`filas`+`scripts`,`carteiras`+`metas_vendedores`,`movimentacoes`,`notas`,`eventos`,`convites`,`campos_personalizados`(+`valores_…`),`candidato`+`candidato_observacao`,`django_*` (auth/sessão/migrations).

### 3.3 Excluídos do modelo (decisão de produto)

Não existem: `class`, `inventory_item`, `inventory_movement`, `Categoria`, `lancamento`, `chancelaria_document*`, `dues_charge`, `member_payment`, `payment_audit_log`, `audit_log`, `auth_attempt`, `refresh_token`, `service_token`, `external_api_audit_log`, `kpi_snapshot`, `password_invite_token`, `_prisma_migrations`.

Critério: manter apenas o que o código realmente usa. Qualquer module futuro que precise deles será desenhado nativamente no novo modelo.

## 4. Regras de negócio

### 4.1 Identidade e nomenclatura

| Na interface | Na base | Notas |
|--------------|---------|-------|
| **Potência** | `prefeitura` | Entidade organizacional; listagem principal |
| **Grão-Mestre** (da Potência) | `prefeitura.prefeito` | Texto livre |
| **Presidente** (da loja) | `loja."deputadoMestreId"` → `member` | Vínculo por membro |
| **Anuidade** | `member.anuidade` | |
| **Situação** | `member.situacao` | `ATIVO` / `INATIVO` |

Branding: bandeira do Reino Unido (`static/img/bandeira-uk.svg`) no login, header, menu e favicon; logo "SAL DA / BRITÂNEA".

### 4.2 Membros

- **Múltiplas lojas por membro** (N:N Na ficha, o membro seleciona *todas* as lojas; a primeira fica como principal).
- **`dataInclusao`** por loja — data de inclusão do membro naquela loja (backfill histórico usa a data de admissão).
- **Sem classe/grau** — filtro de "grau" e coluna "classe" não existem mais; listagem mostra lojas e potências do membro (agregado N:N).
- **Situação binária** ATIVO/INATIVO — é a base do contador BAII no dashboard.
- **Membro sem loja** é válido (select vazio → `member."lojaId" = NULL`).
- Edição preserva as datas de inclusão de lojas já vinculadas.

### 4.3 Potências e lojas

- Potência: CRUD completo (nome, sigla, grão-mestre, telefone, e-mail, endereço, observações, patrono, status). **Sem campo região.**
- Loja: CRUD completo, vínculo 1:N com Potência, Presidente (member), mensalidade, endereço/banco.
- Drill-down: Potência → lojas; Loja → membros.

### 4.4 Autenticação e acesso

- Login por **identificador** (ex.: telefone) + senha.
- Ordem de autenticação: `user` GPRB (bcrypt) → `usuarios` Django (`make_password`).
- Login GPRB cria automaticamente o **espelho local** do usuário (tenant + papel).
- Rate limit de 5 tentativas por identificador.
- Sessão cookie-based; JWT exclusivo para API.

### 4.5 Funil comercial e nichos (herdado do CRM de vendas)

- Etapas fixas: `interessado`, `avaliacao_agendada`, `avaliacao_feita`, `orcamento`, `fechado`, `perdido` — **rótulos adaptados por nicho**, chaves fixas no banco.
- Receita projetada ponderada por etapa (`PESOS_ETAPA`, 10% → 100%).
- Nichos suportados: `saude` (padrão), `odonto`, `imob`, `educacao`, `servicos`, `outro`.
- Princípio: novo nicho é **re-rotulação**, não código novo.

### 4.6 Isolamento multi-tenant

- Toda consulta web é escopada por `tenant_id` da sessão; `admin_saas` (sem tenant) enxerga tudo.
- Dados **nunca** cruzam tenants.
- No uso atual da organização, há um único tenant operacional (código `GPRB`).

## 5. Requisitos funcionais por módulo

### 5.1 Dashboard (`/dashboard/`)
- KPIs do pipeline: funil por etapa, receita projetada, conversão, movimentações recentes.
- Painéis GPRB: membros por situação (BAII), por idade, por potência de origem, por tempo de maçonaria; ranking de lojas por membros; ranking MX (apresentações); próximas sessões; agendamento.
- Contagens e rankings sempre descontando `INATIVO` onde aplicável.

### 5.2 Membros (`/contatos/`)
- Lista com busca, filtro por loja e por situação; colunas de lojas e potências (agregados N:N).
- Ficha completa: dados pessoais, ritualístico (`rito`, `potencia` de origem), endereço, contatos, anuidade, situação.
- Edição com **seleção múltipla de lojas**; criação com lojas opcionais.
- Exclusão com confirmação e visão do vínculo de lojas.

### 5.3 Potências (`/contatos/prefeituras/`)
- Listagem com contagem de lojas e membros por potência.
- CRUD completo **sem região**.
- Drill-down de lojas por potência.

### 5.4 Lojas (`/contatos/lojas/`)
- Listagem com potência, presidente, cidade/UF, situação, total de membros.
- CRUD completo (dados cadastrais, banco, mensalidades).
- Detalhe com membros da loja (ponte N:N + `lojaId`).

### 5.5 Financeiro (`/contatos/financeiro/`)
- **Placeholder** na navegação — módulo a implementar (anuidades/mensalidades via `payment`/`payment_period`).

### 5.6 Funil, tarefas, iniciação (`/funil/`, `/tarefas/`, `/iniciacao/`)
- Kanban drag & drop por etapa; mover via POST.
- Tarefas com vencimento e horário (agenda consolidada).
- Recepção: fluxo de chegada/atendimento com ligação a contatos.

### 5.7 Filiação e congresso
- (**`/candidato/`**) Candidatos com observações e rastreio; impacto: aprovar cria `member`.

### 5.8 Motor marketing-vendas (reaproveitado)
- (**`/automacoes/`**, **`/campanhas/`**, **`/emails/`**, **`/discador/`**, **`/relatorios/`**): automações com passos/execuções, campanhas, e-mails com modelos, filas/scripts, relatórios. Estado funcional deve ser confirmado por verificação individual quando tocados.

## 6. Não-objetivos (fora de escopo)

- ❌ Classes maçônicas (MX/EN/CBCS) e "graus" — **removidos por decisão de negócio**. Não devem retornar nem em relatórios.
- ❌ Campo "Região" em Potência — eliminado; hierarquia fica implícita no nome/vínculos.
- ❌ Controle de inventário, chancelaria/documentos e cobrança de taxas (`dues_charge`) — legados descartados sem uso.
- ❌ Integração `Prisma` — o sistema não mantém espelho com nenhum banco antigo.
- ❌ Multi-banco em runtime — só `saldabritanea`.
- ❌ `docker-compose`/WSL no ambiente de desenvolvimento atual (nativo Windows).

## 7. Métricas de sucesso

| Métrica | Como medir |
|---------|-----------|
| Login e operação 100% no banco novo | `healthz/` + E2E sem banco antigo |
| Cadastros operando (membro com 2+ lojas, N:N) | Casos de teste de ponte `member_loja` |
| Zero referência a classes na UI | Varredura de templates |
| Desligamento físico dos bancos antigos | Validação do usuário antes do `DROP` |

## 8. Roadmap aberto (não priorizado)

1. **Financeiro real** — anuidade/mensalidade sobre `payment`/`payment_period`/`payment_status`; substituir o placeholder.
2. **Importar dados históricos** — migrar `prefeitura`, `loja`, `member`, `member_loja`, `payment` do `saldogprb` (backup já garantido).
3. **Fluxo candidato → membro** — aprovação com criação de membro e vínculo inicial de loja.
4. **Auditoria mínima** - log leve de mudanças nos cadastros (sem voltar às tabelas legadas).
6. **Testes automatizados** da camada GPRB (repositories) com banco de teste dedicado.

## 9. Decisões arquieteturais relevantes (apêndice)

- **Banco único** + **acesso SQL via psycopg3 thread-local** (`core/gprb/connection.py`), fallback de degradação ("modo sem banco") nas telas que usam GPRB.
- **Repositórios** (`repositories/gprb_repository.py`, `dashboard/repositories/gprb_repository.py`) centralizam SQL do modelo GPRB — views não montam SQL.
- **Autenticação híbrida** em `acesso/views/helpers.py` (GPRB-bcrypt → Django) + espelho em `usuarios`.
- **Sem migrations Prisma**; schema GPRB é versionado por scripts em `scripts/` (estrutura de referência da migração em `logs/schema_saldabritanea.sql`).
