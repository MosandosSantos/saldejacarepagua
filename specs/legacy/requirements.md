# Requisitos — SAL DA BRITÂNEA CRM (legado/atual)

> Estado implementado em outubro/2026. Visão de produto completa em `DOCS/PRD.md`.
> Convenção: **RF-xx** = requisito funcional; **RNF-xx** = não funcional. ✅ implementado · 🔶 parcial/placeholder · ⏳ pendente.

## RF-01 · Autenticação e acesso ✅
- Login por identificador (ex.: telefone) + senha em `/login/`.
- Autenticação híbrida: `user` GPRB (bcrypt) → espelho automático em `usuarios` → fallback `usuarios` (Django).
- Rate limit de 5 tentativas por identificador (cache Django).
- Papéis: `admin_saas` (sem tenant, vê tudo), `admin_company`, `operacional`, `viewer` (somente leitura).
- Logout por sessão; JWT exclusivo da API.

## RF-02 · Dashboard (`/dashboard/`) ✅
- KPIs do funil comercial: conversão por etapa, receita projetada ponderada, movimentações recentes.
- Painéis GPRB: membros por situação (BAII ATIVO×INATIVO), por faixa de idade, por potência de origem, por tempo de maçonaria.
- Rankings: lojas por membros (`nome`/`rank`/`total`) e ranking MX por apresentações (`nome`/`rank`/`total_mx`).
- Cache de dashboard (`DashboardCache` + backend Django cache).

## RF-03 · Membros (`/contatos/`) ✅
- Lista com busca, filtro por loja e por situação; colunas agregadas de **lojas** e **potências** (N:N).
- Ficha completa: dados pessoais, ritualístico (rito, potência de origem), endereço, contato, anuidade, situação.
- Edição com **seleção múltipla de lojas** (`getlist('lojas')`); preserva `dataInclusao` das lojas já vinculadas; primeira loja = principal (`member."lojaId"`).
- Membro **sem loja** é válido (`member."lojaId" = NULL`).
- Exclusão com confirmação.
- **Sem classe/grau** — removidos do produto (ver `business-rules.md`).

## RF-04 · Potências (`/contatos/prefeituras/`) ✅
- Listagem com contagem de lojas e membros por potência.
- CRUD completo: nome, sigla, grão-mestre, telefone, e-mail, endereço, observações, patrono, status.
- **Sem campo região** (coluna removida do banco).
- Drill-down JSON de lojas por potência.

## RF-05 · Lojas (`/contatos/lojas/`) ✅
- Listagem: potência, presidente, cidade/UF, situação, total de membros.
- CRUD completo (cadastrais, banco/pix, mensalidades, `contractNumber`).
- Detalhe com membros (via ponte N:N + `lojaId`), drill-down JSON.

## RF-06 · Financeiro (`/contatos/financeiro/`) 🔶
- Placeholder navegável; módulo real (anuidade/mensalidade sobre `payment`/`payment_period`/`payment_status`) pendente.

## RF-07 · Funil comercial (`/funil/`, `/contatos/`) ✅
- Kanban drag & drop por etapa; mover via POST.
- Etapas fixas por chave (`interessado` → `perdido`), rótulos por nicho; receita ponderada por `PESOS_ETAPA`.
- Nichos: `saude` (padrão), `odonto`, `imob`, `educacao`, `servicos`, `outro`.

## RF-08 · Tarefas (`/tarefas/`) ✅
- Follow-ups com vencimento e horário; `/agenda/` redireciona para cá.

## RF-09 · Recepção (`/recepcao/`) ✅
- Fluxo de chegada/atendimento ligado a contatos.

## RF-10 · Filiação (`/candidato/`) ✅
- CRUD de candidatos com observações; vínculo a potência de origem.

## RF-11 · Congresso GEOD-CEOD (`/gestao/`) ✅
- Inscrições: congressistas, tipos de inscrição, pagamentos, capítulos; comunicação/WhatsApp (`/comunicacao/`).

## RF-12 · Motor marketing-vendas 🔶
- `/automacoes/` (automações com passos/execuções), `/campanhas/`, `/emails/` (modelos + envio), `/discador/` (filas/scripts/chamadas), `/relatorios/`.
- Herdados do CRM de vendas; verificar estado funcional módulo a módulo ao tocar.

## RF-13 · Equipe e configuração ✅
- `/equipe/` gestão de usuários do tenant (convites, ativação por token, papéis); `/config/` preferências e tema.

## RF-14 · API REST `/api/v1` ✅
- JWT em `POST /api/v1/auth/login`; rotas de contatos, usuários, tenants, campanhas, carteiras, discador.
- Swagger `/docs` · ReDoc `/redoc`.

## RNF-01 · Multi-tenant ✅
- Escopo obrigatório por `tenant_id`; isolamento entre tenants inegociável.

## RNF-02 · Desempenho ✅
- Conexão psycopg thread-local reutilizada (evita ~15 handshakes por render do dashboard).
- Cache de KPIs de dashboard.

## RNF-03 · Segurança ✅
- Fail-fast em produção sem `DJANGO_SECRET_KEY`/`JWT_SECRET`; cookies Secure + HSTS sem `DJANGO_DEBUG=1`.
- bcrypt no modelo GPRB; `make_password` no modelo Django; templatetag `seguranca` global.
- Rate limit de login; RBAC por papel na API (`test_rbac_api.py`).

## RNF-04 · Banco único ✅
- `saldabritanea` é o único banco em runtime (ORM + SQL GPRB). Sem Prisma, sem bancos externos.

## RNF-05 · Idioma ✅
- Interface e mensagens em **português (Brasil)**; código/identificadores em inglês quando fizer sentido.

## RNF-06 · Observabilidade 🔶
- `/healthz/` valida app + banco. Logs em `logs/`. Sem APM/monitoramento externo.
