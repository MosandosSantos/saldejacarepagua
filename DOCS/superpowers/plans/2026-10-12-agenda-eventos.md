# Agenda de Eventos — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agenda de eventos por loja com presença pós-evento, lembretes por e-mail (48h/24h às 07:00) e exportação via Google Calendar API — escrita negada a tesoureiro e viewer.

**Architecture:** Novo app Django `agenda` (models + views web + management command), reusando `acesso.decorators` (login/tenant) e `contatos.Filiacao` para a lista de presença. Scheduler = management command `agenda_lembretes` idempotente rodando em loop num serviço do compose. Google Calendar atrás de um módulo de serviço mockável.

**Tech Stack:** Django 5.2, PostgreSQL, Tailwind templates existentes, `google-api-python-client` + `google-auth`, SMTP Django existente.

**Spec:** `DOCS/superpowers/specs/2026-10-12-agenda-eventos-presenca-lembretes-design.md`

## Global Constraints

- Roles: escrever em agenda = qualquer role exceto `tesoureiro` e `viewer` (constantes em `acesso/models.py:13-24`).
- Web login sempre via `web_login_required`; escrita escopada por tenant via `filtro_tenant` / `web_requer_tenant_context` (`acesso/decorators.py`).
- Testes: `pytest`, `testpaths = teste`, `DJANGO_SETTINGS_MODULE = core.settings_vale_test` (`pytest.ini`). Login web em teste = seed de sessão como em `teste/test_viewer.py` (`_cliente_web`).
- Nomes de tabela: `agenda_tipos_evento`, `agenda_eventos`, `agenda_presencas`.
- Sem Celery; o command `agenda_lembretes` deve ser idempotente (timestamps `lembrete_48_enviado_em` / `lembrete_24_enviado_em`).
- `core/urls.py:61` tem `path('agenda/', RedirectView...tarefas)` — remover o redirect e incluir o app.

## Review Focus

1. **POST direto de viewer/tesoureiro** → 403 e nenhum dado gravado (botões escondidos não bastam; testar rota por rota). Teste: Task 3.
2. **Re-execução do command na mesma janela** → nenhum e-mail duplicado (timestamp + estado controlam). Teste: Task 6.
3. **Membro sem e-mail ou loja vazia** → envio não quebra; log do pulado. Teste: Task 6.
4. **Presença duplicada para o mesmo membro** → unique(evento, membro); reenvio do form atualiza em vez de duplicar. Teste: Task 4.
5. **Tenant sem `google_calendar_id`** → sync não explode; chip oculto; fluxo normal continua. Teste: Task 5.

---

### Task 1: App `agenda` + models + catálogo

**Files:**
- Create: `agenda/__init__.py`, `agenda/apps.py`, `agenda/models.py`, `agenda/migrations/0001_initial.py`
- Modify: `core/settings.py` (INSTALLED_APPS + `agenda.apps.AgendaConfig`)
- Test: `teste/test_agenda_models.py`

**Interfaces:**
- Produces: `agenda.models.TipoEvento` (nome Char(80) unique, cor Char(7) default `#3b82f6`, db_table `agenda_tipos_evento`); `agenda.models.EventoAgenda` (tenant FK CASCADE, loja FK → `contatos.Loja` PROTECT, tipo FK, titulo Char(200), data_hora DateTimeField, local Char(255), descricao Text blank, criado_por FK→`acesso.Usuario` SET_NULL null, google_event_id Char(120) blank, lembrete_48_enviado_em / lembrete_24_enviado_em DateTimeField null, Meta db_table `agenda_eventos`, ordering `['data_hora']`); `agenda.models.PresencaEvento` (evento FK CASCADE, membro FK→`contatos.Membro` CASCADE, estado choices PRESENTE/AUSENTE/JUSTIFICADO, justificativa Char(255) blank, registrado_por FK Usuario SET_NULL null, registrado_em auto_now, UniqueConstraint `presenca_evento_membro_unica` em (evento, membro), db_table `agenda_presencas`).
- Produces: migration `0001` inclui data migration semeando o catálogo fixo de `TipoEvento`: `('Sessão Magna', '#3b82f6'), ('Assembleia Geral', '#22c55e'), ('Apresentação', '#eab308'), ('Elevação', '#a855f7'), ('Instalação', '#f97316'), ('Aula', '#06b6d4'), ('Outro', '#6b7280')` (get_or_create por nome).

- [ ] **Step 1: Testes falhando** — em `teste/test_agenda_models.py`: (a) `test_tipos_evento_semeados` — após `django_db`, `TipoEvento.objects.count() >= 7` e existe `Sessão Magna`; (b) `test_presenca_unica` — cria evento + membro, cria 2 presenças iguais e espera `IntegrityError`; (c) `test_evento_fields` — dados round-trip de `data_hora`, `lembrete_48_enviado_em`, `google_event_id`.
- [ ] **Step 2:** `docker exec gprbr-app pytest teste/test_agenda_models.py -v` → FAIL (app não existe → models import error).
- [ ] **Step 3:** Criar app/models/migration (`makemigrations agenda` dentro do container) + adicionar a INSTALLED_APPS.
- [ ] **Step 4:** Rodar testes → PASS. `migrate` aplicado no container.
- [ ] **Step 5:** Commit `feat(agenda): app, models and fixed event-type catalog`.

### Task 2: Permissões

**Files:**
- Create: `agenda/permissions.py`
- Test: `teste/test_agenda_permissions.py`

**Interfaces:**
- Consumes: `request.session.get('usuario', {}).get('role')`, constantes `ROLE_TESOUREIRO`, `ROLE_VIEWER` de `acesso.models`.
- Produces: `pode_escrever_agenda(request) -> bool`; `pode_registrar_presenca(request) -> bool` (mesmo conjunto); decorator `agenda_requer_escrita(view_func)` — quando sem permissão: GET/HEAD → `redirect('agenda:lista')`, demais métodos → `HttpResponseForbidden`.

- [ ] **Step 1: Testes falhando** — monkeypatch `RequestFactory` com sessão: role `tesoureiro` → False; `viewer` → False; `secretario`, `presidente_corpo`, `delegado`, `ADM`, `admin_saas` → True; `admin_saas` sem role → False. Decorator: GET chama redirect, POST chama 403.
- [ ] **Step 2:** pytest → FAIL.
- [ ] **Step 3:** Implementar módulo.
- [ ] **Step 4:** pytest → PASS.
- [ ] **Step 5:** Commit `feat(agenda): role permissions excluding treasurer and viewer`.

### Task 3: Views de CRUD (lista / novo / editar / excluir) + urls

**Files:**
- Create: `agenda/views.py`, `agenda/urls.py`, `templates/agenda/lista.html`, `templates/agenda/form.html`, `templates/agenda/excluir.html`
- Modify: `core/urls.py:61` (remover `RedirectView` de `agenda/`; incluir `path('agenda/', include('agenda.urls'))`), `templates/base/basic.html` (item de menu "Agenda", visível a todos, com `_ICONE` seguinte ao padrão de `acesso/context_processors.py`)
- Test: `teste/test_agenda_crud_web.py`

**Interfaces:**
- Consumes: Task 1 models; Task 2 decorator; `filtro_tenant`, `web_login_required`, `web_requer_tenant_context`, `web_requer_edicao`.
- Produces (names em `agenda.urls`, namespace `agenda`): `lista` (GET `/agenda/`), `novo` (GET/POST `/agenda/novo/`, name `novo`), `editar` (GET/POST `/agenda/<int:id>/editar/`, name `editar`), `excluir` (POST `/agenda/<int:id>/excluir/`, name `excluir`). Contexto de lista: `itens` (eventos do tenant ordenados por `data_hora` desc, `select_related('loja','tipo')`), `tipos`, `lojas` (do tenant), filtros GET `loja`/`tipo`. Redirect pós-salvar → `agenda:lista`.

- [ ] **Step 1: Testes falhando** — sessão via helper `_cliente_web` (copiar padrão de `teste/test_viewer.py`): (a) GET `/agenda/` 200 com evento do tenant; evento de outro tenant não aparece; (b) POST `/agenda/novo/` como `secretario` cria `EventoAgenda` e redireciona; (c) POST como `viewer` → 403 e count 0; (d) POST como `tesoureiro` → 403; (e) POST editar muda campos; excluir remove; (f) `admin_saas` sem tenant selecionado em POST → 403 (reuso `web_requer_tenant_context`).
- [ ] **Step 2:** pytest → FAIL.
- [ ] **Step 3:** Implementar views/urls/templates (form Django puro em POST, sem JSON; lojas do form limitadas ao tenant).
- [ ] **Step 4:** pytest → PASS.
- [ ] **Step 5:** Commit `feat(agenda): event CRUD web flows with tenant scoping`.

### Task 4: Presença

**Files:**
- Create: `templates/agenda/presenca.html` (views acrescentadas em `agenda/views.py`, urls em `agenda/urls.py`)
- Test: `teste/test_agenda_presenca_web.py`

**Interfaces:**
- Consumes: `contatos.Filiacao` (membros da loja: `Filiacao.objects.filter(loja_id=evento.loja_id, membro__situacao='ATIVO')`), `PresencaEvento` (Task 1), `agenda_requer_escrita` (Task 2).
- Produces: `presenca` GET `/agenda/<int:id>/presenca/` (name `presenca`) — form com rádio por membro (`presenca_<membro_id>` = PRESENTE/AUSENTE/JUSTIFICADO) e campo `justificativa_<membro_id>`; `presenca_salvar` POST `/agenda/<int:id>/presenca/` (name `presenca_salvar`) — grava tudo em `transaction.atomic()`, `update_or_create` por (evento, membro), `registrado_por` = usuário da sessão, redirect → `agenda:presenca`.

- [ ] **Step 1: Testes falhando** — (a) GET lista só membros ATIVOS filiados à loja do evento (nome presente, membro de outra loja ausente); (b) POST salva 3 estados + justificativa; (c) POST repetido atualiza, count de PresencaEvento fica igual; (d) GET/POST como viewer → redirect/403 e nada gravado.
- [ ] **Step 2:** pytest → FAIL.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** pytest → PASS.
- [ ] **Step 5:** Commit `feat(agenda): post-event attendance registration per loja`.

### Task 5: Google Calendar sync

**Files:**
- Create: `agenda/google_sync.py`
- Modify: `acesso/models.py` (campo `google_calendar_id = models.CharField(max_length=120, blank=True, default='')` em `Tenant` + migration), `requirements.txt` (`google-api-python-client>=2.100`, `google-auth>=2.20`), `agenda/views.py` + `agenda/urls.py` (ação `google_sync` POST `/agenda/<int:id>/google/`, name `google_sync`), `templates/agenda/lista.html` (chip sync)
- Test: `teste/test_agenda_google_sync.py`

**Interfaces:**
- Consumes: env `GOOGLE_SERVICE_ACCOUNT_JSON` (caminho ou JSON inline) e `Tenant.google_calendar_id`.
- Produces: `agenda/google_sync.py`: `sincronizar_google(evento) -> str|None` (retorna `google_event_id` ou None se não configurado), `remover_google(evento) -> bool` (best-effort, nunca levanta). Autenticação: `service_account.Credentials.from_service_account_info/.from_service_account_file` + `.with_subject` delegação quando `GOOGLE_WORKSPACE_ADMIN` definido; escopo `https://www.googleapis.com/auth/calendar`. Views: POST marca `google_event_id` ou deixa None; chip "Sincronizado ✓" quando `google_event_id`, botão "Enviar ao Google Calendar" quando não; nenhum botão se tenant sem `google_calendar_id`.
- Nota: sem credencial real no ambiente, os testes mockam; o fluxo com credencial real fica verificado manualmente em homologação.

- [ ] **Step 1: Testes falhando** — (a) `Tenant.google_calendar_id` existe (round-trip); (b) tenant sem calendar_id → `sincronizar_google` retorna None e view não quebra (200/302); (c) com calendar_id + google client mockado (monkeypatch em `agenda.google_sync._client`) → `google_event_id` salvo; (d) `remover_google` engole exceção e retorna False.
- [ ] **Step 2:** pytest → FAIL.
- [ ] **Step 3:** Implementar campo, migration, módulo, view, chip.
- [ ] **Step 4:** pytest → PASS.
- [ ] **Step 5:** Commit `feat(agenda): Google Calendar service-account sync with tenant calendar`.

### Task 6: Lembretes por e-mail + command

**Files:**
- Create: `agenda/emails.py`, `agenda/management/commands/agenda_lembretes.py`, `agenda/management/__init__.py`, `agenda/management/commands/__init__.py`, `templates/agenda/emails/lembrete.html`, `templates/agenda/emails/lembrete.txt`
- Test: `teste/test_agenda_lembretes.py`

**Interfaces:**
- Consumes: `EventoAgenda` (timestamps de Task 1), `Filiacao` (destinatários), SMTP de `core/settings.py` (EMAIL_HOST/USER/PASSWORD; `EMAIL_CONFIGURADO` em `core/settings.py:352`).
- Produces: `agenda/emails.py`: `destinatarios_do_evento(evento) -> list[str]` (membros ATIVOS por Filiacao com email não vazio, dedup, case-insensitive) e `enviar_lembretes(evento, estado: '48'|'24', agora=None) -> int` — só envia se horário local cai na janela de 07:00 do dia D-2/D-1 dentro de ±11 min do agora, timestamp nulo, e `EMAIL_CONFIGURADO`; envia, marca timestamp, retorna qtd enviada; destinatário sem e-mail pulado (log), falha SMTP → exceção propagada (sem marcar timestamp); `agenda_lembretes` command: itera eventos de hoje+49h com timestamps nulos, chama enviar; imprime `48h=X 24h=Y`.

- [ ] **Step 1: Testes falhando** — TZ fixa via `override_settings(TIME_ZONE='America/Sao_Paulo', USE_TZ=True)`: (a) evento em D-2 07:10 e `agora` 07:05 → envia (monkeypatch `django.core.mail.send_mail` contando) e marca timestamp; (b) re-executar com mesmo `agora` → 0 enviados; (c) evento às 07:10 e agora 15:00 → não envia; (d) membro sem e-mail → não conta e não quebra; (e) smtplib falho (monkeypatch) → timestamp continua nulo.
- [ ] **Step 2:** pytest → FAIL.
- [ ] **Step 3:** Implementar módulo + command + templates (assunto `[<loja>] <titulo> — <data>`; corpo com título, tipo, data/hora local, local, link `/agenda/`).
- [ ] **Step 4:** pytest → PASS.
- [ ] **Step 5:** Commit `feat(agenda): idempotent 48h/24h email reminder command`.

### Task 7: Serviço cron no compose + env

**Files:**
- Modify: `docker-compose.yml` (serviço `agenda-cron` reusando a imagem do app: `command: sh -c "while true; do python manage.py agenda_lembretes --loop; sleep 300; done"` — variant: no interval embutido no command, `--loop` flag faz o `while`; depends_on db unhealthy-guard igual aos demais; `restart: unless-stopped`), `.env.example` (GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_CALENDAR_ID, GOOGLE_WORKSPACE_ADMIN comentados), `agenda/management/commands/agenda_lembretes.py` (flag `--loop`: roda uma vez e sai por padrão)
- Test: sem novo arquivo — verificação manual (Step 4)

- [ ] **Step 1:** Ajustar command para suportar `--loop` e execução única.
- [ ] **Step 2:** Adicionar serviço no compose + env de exemplo.
- [ ] **Step 3:** `docker compose up -d agenda-cron` no ambiente local; `docker compose logs agenda-cron --tail 20` mostra a linha do command (execução única no start) e container `Up`. Rodar `pytest teste/test_agenda_lembretes.py` de novo (regressão).
- [ ] **Step 4:** Commit `feat(agenda): compose cron service for reminders`.

### Task 8: Wiring final (redirect, documento, smokes)

**Files:**
- Modify: `core/urls.py` (conferir redirect antigo removido na Task 3 — smoke final), `templates/base/basic.html` — confirmar item de menu
- Test: `teste/test_agenda_smoke.py`

- [ ] **Step 1: Testes falhando** — (a) GET `/agenda/` não responde mais com redirect para `tarefas:lista`; responde 200 do app (login exigido); (b) GET `/agenda/` sem sessão → redirect `/login/`.
- [ ] **Step 2:** pytest → FAIL (se a Task 3 já cobriu, os testes passam de primeira — validar e manter).
- [ ] **Step 3:** Corrigir o que faltar (menu/context processor).
- [ ] **Step 4:** Suite completa: `docker exec gprbr-app pytest teste/ -q` → PASS (nenhum teste pré-existente quebrado).
- [ ] **Step 5:** Commit `feat(agenda): route wiring and smoke coverage`.
