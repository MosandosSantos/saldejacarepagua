# Revisão de Segurança e Qualidade — Sprints & PRDs

> Data: 03/09/2026 · Escopo: código Django web (apps `acesso`, `contatos`, `dashboard`, `funil`,
> `emails`, `tarefas`, `automacoes`, `campanhas`, `discador`, `relatorios`, `gestao`, `core`).
> Método: leitura de settings/urls/views/templates, análise AST de código morto, greps de padrões de
> risco e conferência de rotas públicas.
>
> **Postura já existente (não re-abrir):** settings fail-closed (DEBUG/SECRET_KEY/JWT exigidos em
> produção), cookies HttpOnly+SameSite, CSP, HSTS, rate limit de login, decorators de RBAC
> (`web_login_required`, `web_requer_edicao`, `filtro_tenant`), SQL parametrizado (as f-strings
> encontradas interpolam apenas fragmentos fixos; valores sempre via `%s`), proteção de CSV injection
> (`_csv_seguro`) e open-redirect bloqueado no rastreio de clique (só http/https).

---

## Severidade

| Classe | Definição |
|---|---|
| **Alta** | XSS armazenado/executável ou risco de segurança explorável |
| **Média** | Endurecimento, dados externos não confiáveis, duplicidade que gera bugs |
| **Baixa** | Código morto, apps sem menu, higiene |

---

# SPRINT 1 — Sanear injeção de dados do banco em `<script>` (XSS)

> **Tema transversal:** o app lê de um banco **compartilhado/legado (SAL GPRB)** cujos dados
> (nomes de loja, membros, ritos, potências, categorias) **não podem ser tratados como confiáveis**.
> Vários templates embutem esses dados em blocos `<script>` via `{{ x|safe }}` e/ou re-injetam via
> `innerHTML` — vetores de stored/dom XSS e de JS quebrado.

## PRD 1.1 — Trocar `|safe` de JSON/JS por serialização segura (json.dumps + escape `\u003c` ou filtro `json_script`)

**Problema:** a maioria dos pontos usa `{{ dados|safe }}` direto. Quando o valor é uma *lista/dict
Python* (não JSON), o `str()` vira repr Python injetado em JS — e, pior, strings vindas do banco com
`</script>`, `'` ou aspas quebram o script e podem executar código arbitrário.

**Evidências (armazenado → `<script>`/`innerHTML`):**
- `dashboard/templates/dashboard/index.html` linhas 217–218, 276, 341, 406, 498 — `ritodados`,
  `idade_dados`, `potencia_dados`, `tempo_maconaria_dados` (nomes de ritos/potências vêm do banco).
- `dashboard/templates/dashboard/partials/_agendamento.html` linha 26 (`agendamento_dados`) + linhas
  46–52 — `d.loja` (nome de loja do banco) concatenado em `innerHTML` **sem escapar HTML**.
- `tarefas/templates/tarefas/ranking.html` linhas 143–145 — `ranking_rows`, `meetings`, `attendances`
  (nomes de membros e títulos de sessão do banco).
- `gestao/templates/gestao/dashboard.html` linhas 163–199 — o comentário afirma "via json_script
  (NUNCA |safe)" mas o código usa `|safe` com `json.dumps` sem escapar `<` → `</script>` num rótulo
  (categoria, tipo, nome) quebra o bloco.
- `automacoes/templates/automacoes/formulario.html` linhas 105, 127–128 — `passos_json` escapa `<`
  (linha 263 da view) mas `membros_json`/`modelos_json` **não** (linhas 261–262 da view) — nomes de
  contatos/modelos entram crus no JS.
- `discador/templates/discador/operador.html` linha 194 — `status_opcoes|safe`.

**Proposta:**
1. Criar filtro/método único (ex.: `core/templatetags/seguro.py` com filtro `js_obj`) que faça
   `json.dumps(value, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&','\\u0026')`
   e usar `{{ x|js_obj }}` (sem `|safe`).
2. Nos casos com **HTML gerado** (`_agendamento.html`), escapar a string antes do `innerHTML`
   (helper `esc` em JS) ou renderizar com `textContent`.
3. Em `_agendamento.html`, trocar a tabela re-renderizada por `<template>`/`textContent`.

**Aceite:** nenhum `|safe` alimentando `<script>` ou `innerHTML` com dado de banco sem o filtro;
teste automatizado injetando `</script><script>alert(1)</script>` num nome de loja/rito/categoria e
verificando resposta saneada (sem execução).

## PRD 1.2 — Corrigir XSS em atributos `onclick` com `confirm('...{{ var }}...')`

**Problema:** dados do banco interpolados dentro de strings JS em atributos HTML. O escape HTML do
Django protege o atributo, mas `&#x27;` é decodificado pelo parser antes do JS executar → apóstrofo
vira quebra de string JS (XSS clássico em handler inline).

**Evidências:**
- `acesso/templates/acesso/config.html` linhas 247 (`Excluir a etapa "{{ e.nome }}"`) e 473
  (`Transferir a propriedade... {{ m.nome }}`).
- `emails/templates/emails/lista.html` linha 118 (`Excluir o modelo "{{ m.nome }}"`).
- `emails/templates/emails/campanha.html` linha 57 (número — risco menor).

**Proposta:** remover `confirm()` inline. Padrão: botão com `data-confirm="Mensagem fixa"` +
delegated listener que usa `event.preventDefault()`/`submit()` e exibe a mensagem via
`textContent`; quando a mensagem precisa do nome, usar `data-nome` e montar com `textContent`.

**Aceite:** zero `onclick="return confirm('{{` restantes no projeto; página de config renderiza nome
hostil (`x');alert(1)//`) sem quebrar o atributo.

## PRD 1.3 — `autores` no DOM de dashboard: eliminar `|safe` de SVG com dados do banco

**Problema:** `timeline_svg|safe`, `funil_svg|safe`, `baii_svg|safe` e `grafico_atividade|safe` são
SVGs montados por f-strings. Hoje interpolam apenas números/cores fixas (seguro), mas `_linhas_svg`
(relatorios) interpola `_rotulo` e `serie[i]["data"]` em `<title>`/`<text>` — rotulos hoje são fixos,
porém a função aceita dados arbitrários e qualquer refactor futuro com nome de membro vira XSS.

**Proposta:** nos builders `_funnel_svg`/`_baii_svg`/`_timeline_svg`/`_linhas_svg`, aplicar
`html.escape()` (e, em atributos, escapar aspas) em **todo** texto interpolado; adicionar teste de
regressão com nome contendo `<`/`>`/`"`.

**Aceite:** teste que passa string hostil ao builder e garante saída escapada.

---

# SPRINT 2 — Endurecer configuração e rotas públicas

## PRD 2.1 — Rejeitar segredos placeholder em produção

**Problema:** `.env.example` usa `DJANGO_DEBUG=0` com `DJANGO_SECRET_KEY=troque-por-um-segredo-longo-e-aleatorio`
e `JWT_SECRET=troque-por-outro-...`. Quem copiar `.env.example` → `.env` sobe com **DEBUG=0** mas
chave **conhecida** (diferente do `_DEV_SECRET` interno, então o guard atual não dispara).

**Proposta:** em `core/settings.py`, além do `_DEV_SECRET`, rejeitar valores que comecem com
`troque-por-` quando `DEBUG=0` (mesmo padrão fail-fast dos blocos S8/C2).

**Aceite:** `manage.py check` falha com `ImproperlyConfigured` claro se DEBUG=0 + secret placeholder.

## PRD 2.2 — Revisar cache e rate limit em produção multi-processo

**Problema:** `CACHES` usa `LocMemCache` mesmo em produção. Rate limit de login e os contadores de
captura/invalidação de sessão ficam por-processo → em deploy com 2+ workers o limite efetivo
multiplica e o bloqueio é inconsistente. (Comentário no settings já reconhece; falta plano.)

**Proposta:** documentar + permitir `REDIS_URL` para `RedisCache` em produção (fallback LocMem em
dev); teste que o botão `DJANGO_RATE_LIMIT=0` dos testes continua funcionando.

**Aceite:** com `REDIS_URL` setada, rate limit e sessões usam Redis; sem ela, dev continua LocMem.

## PRD 2.3 — Conexão GPRB: exigir TLS/timeout quando remota

**Problema:** `core/gprb.py::connect()` usa psycopg sem `sslmode` nem `connect_timeout`. Em dev
(localhost) é ok; se o banco GPRB for acessado de outro host, credenciais trafegam sem TLS e uma
queda do banco segura a request sem timeout.

**Proposta:** aceitar `GPRB_DB_SSLMODE` (default `prefer`/`require` quando host ≠ 127.0.0.1/localhost)
e `GPRB_DB_TIMEOUT` (default 10s); `connect_timeout` no `psycopg.connect`.

**Aceite:** função de conexão recebe parâmetros de env; timeout presente; documentado no `.env.example`.

## PRD 2.4 — Revisar endpoints públicos

**Problema:** `healthz`, `/emails/aberto/<token>/`, `/emails/clique/<token>/<codigo>/`,
`/captura/<token>/`, `/convidar/<token>/` são públicos por design. Verificado: captura tem honeypot +
rate limit por IP (cache), clique valida esquema http/https, convidar usa token. **Riscos residuais:**
token de captura/convidar são PKs/`str` no path (enumeráveis? conferir se `token_captura` é
aleatório), e o rate limit por IP depende do cache (ver PRD 2.2).

**Proposta:** auditar geração/entropia dos tokens (`Tenant.token_captura`, convite) e documentar
decisão; garantir `captura` rejeita token de tenant inativo e convidar revalida expiração.

**Aceite:** checklist documentado no `DOCS/security.md`; tokens com entropia ≥ 128 bits ou validação
de expiração explícita.

---

# SPRINT 3 — Código morto, "viúvas" e apps sem referência no menu

## PRD 3.1 — Remover função órfã `deputados_mestres`

**Problema:** única ocorrência no projeto é a própria definição
(`core/gprb.py:510`) — sobrou da troca do card "Deputados Mestres" por "Próximas Sessões". Consulta
inútil ao banco (sem callers).

**Proposta:** deletar a função (e, se nenhum teste a usa — confirmado, nenhum —, nada mais).

**Aceite:** `grep -r deputados_mestres` → vazio; `manage.py check` ok.

## PRD 3.2 — Decidir destino dos apps **sem entrada no menu**

**Problema:** `gestao`, `relatorios`, `discador`, `automacoes` e a listagem de `tarefas`
(`tarefas:lista`) não têm item no nav (`acesso/context_processors.py::_ROTAS` lista apenas Dashboard,
Funil, Membros, Prefeitura, Lojas, Ranking e Comunicações▾). O app **`gestao`** (GEOD-CEOD) não tem
**nenhuma** referência em menu/template fora dele mesmo; `discador` só aparece como âncora de config;
`automacoes`/`relatorios` ficam acessíveis apenas por URL digitada.

**Proposta (decisão de produto):**
- Se são áreas ativas: adicionar itens/subitens no menu (ex.: Comunicações▾ ganha Automações; novo
  grupo "Operação" com Discador, Relatórios; Gestão/GEOD separado por papel `admin_saas`).
- Se são experimentais/internas: manter **fora** de `_ROTAS` mas documentar em
  `DOCS/architecture.md` e dar entrada via link contextual (dashboard/config), evitando "funil morto".

**Aceite:** após a mudança, todo app em `INSTALLED_APPS` com urls tem entrada navegável **ou** está
documentado como área interna com link de entrada; teste de smoke renderiza nav sem `NoReverseMatch`.

## PRD 3.3 — Revisar rotas legadas do app `contatos`

**Problema:** `contatos/urls.py` mantém CRUD "CRM HAZON" (`novo`, `<int:pk>/`, negócios, notas, tags,
leads-pobres, carteiras, campos) **e** o CRUD GPRB (membros/lojas/prefeituras). Templates antigos
(`detalhe.html`, `formulario.html`, `negocio_form.html`, etc.) e views legadas coexistem com o fluxo
GPRB. Não é duplicidade "inocente": mantém duas filosofias (int pk + modelos ORM vs UUID + SQL cru).

**Proposta:** inventariar quais rotas legadas ainda recebem tráfego (analytics/uso) e marcar num PRD
de produto a migração/remoção; no mínimo, documentar no `DOCS/architecture.md` a separação
"contatos HAZON (legado)" vs "GPRB (atual)" para que futuras alterações não atinjam a camada errada.

**Aceite:** doc atualizado + lista de rotas candidatas à remoção com dono.

---

# SPRINT 4 — Duplicidade que gera bug

## PRD 4.1 — Centralizar envio de e-mail

**Problema:** a lógica "simulação vs SMTP" e a montagem do `EmailMessage` estão duplicadas:
- `emails/servico.py::enviar_um` (canônico);
- `relatorios/management/commands/enviar_relatorio.py` reimplementa simulação + `EmailMessage`
  (linhas 56–88) e **redefine** `EMAIL_VAZIO` (constante já existe em `emails/servico.py`);
- `emails/views.py::enviar_contato` (linhas ~223–236) duplica o bloco "criar registro + anexar
  pixel + salvar + enviar" de `servico.disparar_campanha`.

Divergências entre os três (ex.: um trata erro por envio, outro aborta) já causaram comportamento
diferente entre "enviar um" e "disparar campanha".

**Proposta:** criar `core/email.py` (ou ampliar `emails/servico.py`) com `enviar_simples(assunto,
corpo, destinatario, anexo=None)` e fazer os três pontos chamarem a mesma rotina; mover `EMAIL_VAZIO`
para um único módulo e importar nos usos.

**Aceite:** `grep -rn "EmailMessage("` → apenas o módulo central; comando `enviar_relatorio` usa o
mesmo caminho de simulação do servico.

## PRD 4.2 — Fatorar o acesso ao banco GPRB nas views de `contatos`

**Problema:** `contatos/views/crud.py` tem 15 funções com `from core.gprb import connect` e repete o
snippet `SELECT id FROM tenant WHERE code = 'GPRB'` **7 vezes** (além de "usar tenant da sessão" vs
"GPRB fixo" inconsistente em `tarefas/views.py`, que usa `tenant_id` da sessão). Cada mudança de
esquema/regra de tenant exige editar N pontos.

**Proposta:** helper `core/gprb.py::tenant_id(conn, code='GPRB')` (cacheado por request) + view de
apoio `membro do tenant da sessão`; refatorar crud.py para usar helpers únicos por consulta.

**Aceite:** zero repetição do snippet de tenant fora do helper; testes existentes seguem verdes.

## PRD 4.3 — Unificar builders de gráfico SVG

**Problema:** `dashboard/views.py` mantém `_funnel_svg` e `_baii_svg` praticamente idênticos (o
segundo nasceu como cópia trocando cores), e `relatorios/views.py::_linhas_svg` repete o mesmo
padrão de defs/camadas/legenda. Além de manutenção dobrada, é onde mora o risco do PRD 1.3.

**Proposta:** mover os builders para um módulo `core/graficos.py` com um builder 3D genérico
(paleta por parâmetro) e um de linhas; dashboard/relatorios só passam dados.

**Aceite:** nenhuma função de gráfico duplicada entre apps; saída visual igual (comparar screenshots).

---

# SPRINT 5 — Higiene e dívidas menores

- **PRD 5.1 · Duplicidade de `_months_between`/`_years_between`:** já centralizadas em `core/gprb.py`
  e importadas por `tarefas/views.py` — **OK, não mexer** (registro de verificação).
- **PRD 5.2 · f-strings em SQL:** as interpolações são de fragmentos estáticos com valores sempre por
  `%s` — **OK**; registrar no guia de contribuição que novo código deve usar apenas concatenação
  controlada de cláusulas fixas + parâmetros (sem formatação de valores).
- **PRD 5.3 · `gestao` sem teste no CI:** confirmar se `gestao` está coberto por testes; o app é o
  único com `INSTALLED_APPS` + urls + sem menu (ver PRD 3.2).
- **PRD 5.4 · Segredos em seed:** `seed_usuarios.py`/`seed_dados.py` imprimem senhas e gravam
  `.env-seed` (gitignored) — aceitável para demo; garantir que nunca rode em produção (guard por
  `DEBUG` ou flag `--force`).

---

## Resumo de prioridades

| # | Título | Severidade | Esforço |
|---|---|---|---|
| 1.1 | Serialização segura p/ dados de banco em `<script>`/`innerHTML` | Alta | M |
| 1.2 | XSS em `onclick=confirm('...')` | Alta | P |
| 1.3 | Escape em builders de SVG | Média | P |
| 2.1 | Rejeitar segredos placeholder em produção | Alta | P |
| 2.2 | Cache/rate limit em produção | Média | M |
| 2.3 | Conexão GPRB com TLS/timeout | Média | P |
| 2.4 | Auditoria de tokens públicos | Média | P |
| 3.1 | Remover `deputados_mestres` (órfã) | Baixa | P |
| 3.2 | Apps sem menu: decidir destino | Média (produto) | M |
| 3.3 | Inventariar rotas legadas do contatos | Baixa | M |
| 4.1 | Centralizar envio de e-mail | Média | P |
| 4.2 | Fatorar acesso GPRB nas views | Média | M |
| 4.3 | Unificar builders de SVG | Baixa | M |
| 5.x | Higiene (verificações ok + docs) | Baixa | P |

---

# Execução dos Sprints 1 e 2 (2026-09-03)

Status de cada PRD após a implementação:

| PRD | Status | Evidência / mudanças |
|---|---|---|
| 1.1 | ✅ Implementado | Filtro `js` (JSON seguro p/ `<script>`) em `core/templatetags/seguranca.py`, registrado como builtin e via app `core` no INSTALLED_APPS. Aplicado em `dashboard/index.html` (chart/rito/idade/potência/tempo), `_agendamento.html`, `tarefas/ranking.html`, `gestao/dashboard.html` (16 vars) e `discador/operador.html` (corrige também JSON inválido de `Chamada.STATUS`). Em `automacoes`, os JSONs de `passos`/`membros`/`modelos` são escapados na view (`.replace('<','\u003c')` etc.). `innerHTML` com dados do banco (ranking, agendamento) agora escapa via função `esc()`. |
| 1.2 | ✅ Implementado | `confirm('...{{ var }}...')` inline removido (config.html ×5, emails/lista, emails/campanha, automacoes/lista). Substituído por `data-confirm` (contexto HTML, escapado) + listener delegado global em `templates/base/basic.html`. Sem `{{ }}` restante em strings JS de onclick/onsubmit. |
| 1.3 | ✅ Verificado + escape | Builders de SVG (`_funnel_svg`, `_baii_svg`) só interpolam cores validadas como hex (não-hex quebra em `_shade` → 500, nunca XSS), inteiros e datas formatadas. Ainda assim, cores vindas da config do banco agora passam por `_esc_attr` (html.escape). `_timeline_svg`/`_linhas_svg` (relatorios) não interpolam texto de usuário. |
| 2.1 | ✅ Implementado | `settings.py`: além do `_DEV_SECRET`, produção rejeita chaves placeholder (marcadores tipo "troque", "change-me", "placeholder"…) com `ImproperlyConfigured` — verificado com DEBUG=0 (placeholder aborta; chave forte sobe). `.env.example` já coberto (contém "troque"). |
| 2.2 | ✅ Implementado | `CACHES` usa `RedisCache` do Django quando `REDIS_URL`/`REDIS_TLS_URL` existir (rate limit compartilhado entre workers); senão LocMem (dev). `redis>=4.5` adicionado ao `requirements.txt`. |
| 2.3 | ✅ Implementado | `core/gprb.py::connect()` agora passa `sslmode` (default `prefer`, configurável via `GPRB_DB_SSLMODE`) e `connect_timeout=10` (`GPRB_DB_TIMEOUT`). Conexão local validada. |
| 2.4 | ✅ Implementado | `token_captura` passa a ser gerado com `secrets.token_urlsafe(32)` (256 bits) em `acesso/models.py::token_captura_do_tenant` e no regen em `acesso/views.py`. Convites já usavam 32. Migration histórica 0006 mantida. |

**Verificação:** `manage.py check` limpo; 11 templates alterados compilam; py_compile ok; baseline de testes inalterada (dashboard: 9 ok, 3 falhas pré-existentes não relacionadas).

**Sprint 3 (executado em 2026-09-03):** 3.1 ✅ `deputados_mestres` removida de `core/gprb.py` (era a única ocorrência; `grep` limpo, check ok); 3.2 ✅ menu decidido pelo dono: `acesso/context_processors.py::_ROTAS` enxuto — Dashboard, Funil, Membros, Prefeitura, Lojas, **Ranking (solo, com badge)**, **Comunicações** (link único para `premium_campanhas`, sem furar o upsell) e **Equipe** (novo item, visível só para `admin_company`, com gate por papel no builder do nav). Sem submenus de Tarefas/Operação (Discador/Relatórios/Automações por URL). `gestao` fica como área interna documentada (dashboard global sem tenant); 3.3 ✅ inventário documentado em `DOCS/architecture.md` (tabela "`contatos`: duas camadas" + rotas sem entrada na UI, veredito por rota).

**Sprint 4 (parcialmente executado em 2026-09-03):**

**4.1 ✅ Centralizar envio de e-mail** — `emails/servico.py` agora tem duas rotinas únicas:
- `enviar_mensagem(assunto, corpo, destinatario, anexo=None, anexo_nome=..., conteudo_tipo=...)` — única checagem "simulação vs SMTP" + `EmailMessage` (com suporte a anexo); retorna `'enviado' | 'simulado' | 'erro'`.
- `registrar_e_enviar(modelo, contato, base_url, campanha=None)` — único fluxo "criar registro + render + pixel/links + salvar + enviar", usado por `disparar_campanha` e pelo envio individual.
`enviar_um` foi reimplementado sobre `enviar_mensagem` (sem mudança de comportamento).
- `emails/views.py::enviar_contato` agora chama `registrar_e_enviar` (imports mortos removidos).
- `relatorios/management/commands/enviar_relatorio.py` deixou de redefinir `EMAIL_VAZIO` (importa de `emails.servico`) e de reimplementar SMTP/simulação: usa `enviar_mensagem(..., anexo=pdf)`, mantendo a contagem e as mensagens de saída.
- Verificação: `py_compile` + `manage.py check` limpos; `test_fase_o_email_avancado.py` 21/21 ok; módulos de export/campanhas/relatórios/automações: 73 ok / 6 falhas **comprovadamente pré-existentes** (reproduzem com o código do HEAD antes do 4.1).

**Pendente:** 4.2 fatorar acesso GPRB nas views; 4.3 unificar builders SVG.
