# Spec: Agenda de eventos com presença, lembretes por e-mail e exportação Google Calendar

**Status:** aguardando revisão do usuário

**Data:** 2026-10-12

## Objetivo

Criar a agenda de eventos do sistema: qualquer perfil pode consultar; criar, editar e excluir é permitido a todos **exceto tesoureiro e viewer**. Cada evento pertence a uma loja. Depois do evento, secretário ou presidente registram a presença dos membros a partir de uma lista da loja. O evento pode ser exportado via API do Google Calendar. Dois lembretes por e-mail são enviados aos membros da loja: 48 h e 24 h antes, sempre às 07:00.

## Decisões confirmadas

- Perfis autorizados a escrever: todos menos **tesoureiro** e **viewer** (secretário, presidente, delegado, ADM, admin_saas).
- Evento vinculado a **uma loja**; a lista de presença deriva das filiações daquela loja.
- **API do Google Calendar** (não arquivo .ics) para a exportação.
- **Dois lembretes** por evento: 48 h antes às 07:00 e 24 h antes às 07:00, para os membros ativos da loja.
- Os tipos de evento parte de um catálogo fixo do rito.
- Scheduler escolhido: **container cron no `docker-compose.yml`** executando um management command Django (o projeto não usa Celery hoje).
- Os ritos oficiais já foram cadastrados nos 5 tenants: ADON, BRAS, EMUL, MODE, REAA, RER, SHOR, YORK.

## Abordagens consideradas (scheduler)

1. **Container cron no compose (selecionada):** serviço dedicado rodando o command em loop. Isolado, observável, barato; idempotência evita duplicação em re-rodadas.
2. **Celery + Beat:** padrão industrial e préparado para mais tarefas futuras, mas exige worker + beat novos e mais infra.
3. **APScheduler no processo Django:** sem container extra, porém acopla o agendamento ao ciclo de vida do app e fica menos previsível em reinícios.

## Modelagem de dados (app `agenda`)

### `TipoEvento` (tabela `agenda_tipos_evento`)

- `nome` Char(80) — catálogo fixo: Sessão Magna, Assembleia Geral, Apresentação, Elevação, Instalação, Aula, Outro.
- `sigla`/`cor` Char(7) — badge na UI.
- Catálogo global, compartilhado entre tenants; sem FK tenant.

### `EventoAgenda` (tabela `agenda_eventos`)

- `tenant` FK → `acesso.Tenant` (CASCADE).
- `loja` FK → `contatos.Loja` (PROTECT).
- `tipo` FK → `agenda.TipoEvento`.
- `titulo` Char(200); `data_hora` DateTimeField (com timezone); `local` Char(255); `descricao` Text (opcional).
- `criado_por` FK → usuário (SET_NULL).
- `google_event_id` Char — id retornado pela API do Google (controle de sync).
- `lembrete_48_enviado_em` / `lembrete_24_enviado_em` DateTimeField nulos — idempotência dos lembretes (rodar 2 x não duplica).
- Índice na `data_hora` para a janela do scheduler.

### `PresencaEvento` (tabela `agenda_presencas`)

- `evento` FK → `EventoAgenda` (CASCADE); `membro` FK → `contatos.Membro` (CASCADE).
- `estado` choice: PRESENTE / AUSENTE / JUSTIFICADO; `justificativa` Char(255) opcional quando JUSTIFICADO.
- `registrado_por` FK usuário, `registrado_em` DateTime.
- UniqueConstraint (evento, membro).
- A lista de candidatos vem de `Filiacao` da loja do evento — não duplica relacionamento membro↔loja.

## Permissões

Regras centralizadas em `agenda/permissions.py`, reusando `web_login_required`, `web_requer_tenant_context` e `filtro_tenant` do acesso:

| Perfil | Criar/Editar/Excluir | Registrar presença | Ver agenda |
|---|---|---|---|
| tesoureiro | ❌ | ❌ | ✅ |
| viewer | ❌ | ❌ | ✅ |
| secretario / presidente | ✅ | ✅ | ✅ |
| delegado / ADM / admin_saas | ✅ | ✅ | ✅ |

- Escopo: leitura e escrita escopadas pelo tenant da sessão; `admin_saas` vê tudo (com tenant selecionado para escritas, como hoje).

## Fluxos web

1. **`/agenda/`** — lista compacta (cards) com eventos futuros e passados da loja/tenant: badge do tipo com sua cor, título, data/hora, local; filtro por loja e por tipo. Ações no card: editar/excluir (perfis de escrita), "Registrar presença" (aparece a partir da `data_hora`, só para quem pode), chip "Enviar ao Google Calendar" / "Sincronizado ✓" / "Erro de sync (reenviar)".
2. **`/agenda/novo/`** e **`/agenda/<id>/editar/`** — form: loja (select do tenant), tipo, título, data/hora, local, descrição. Ao salvar não há UI extra: os dois lembretes ficam implícitos pela data e são disparados pelo scheduler. Evento com data no passado é permitido (registro retroativo), com banner informativo.
3. **`/agenda/<id>/presenca/`** — lista dos membros ativos filiados à loja com rádio Presente/Ausente/Justificado (+campo justificativa em JUSTIFICADO); botão salva tudo numa única transação. Após salvar, chip no card: "Presença registrada (n/total)".
4. **Excluir** — cascata nas presenças; se sincronizado, tenta deletar no Google (best-effort).

## Google Calendar

- Bibliotecas novas: `google-api-python-client` + `google-auth` no `requirements.txt`.
- Autenticação: **Service Account** com delegação no Workspace da Potência (o evento é institucional da loja; OAuth por usuário tem mais fricção).
- Config por env: `GOOGLE_SERVICE_ACCOUNT_JSON` (path ou JSON inline) e `GOOGLE_CALENDAR_ID` **por tenant** (novo campo nullable em `acesso.Tenant`).
- Fluxo: botão no card chama view; cria o evento na API, guarda `google_event_id`, chip vira "Sincronizado ✓". Edição/exclusão propagam update/delete (retry único; falha mantém chip "Erro de sync" com reenvio manual).
- Tenant sem `GOOGLE_CALENDAR_ID` configurado: botão oculto e instrução no admin do tenant.

## Lembretes por e-mail

- Dois disparos por evento, às **07:00** locais: 48 h e 24 h antes de `data_hora`.
- Destinatários: membros **ATIVOS** daquela loja (via `Filiacao`) com e-mail preenchido; sem e-mail → pulado e logado (não bloqueia).
- Envio por o SMTP existente (Gmail) em `core/settings.py`; template HTML `agenda/templates/agenda/emails/lembrete.html` + versão texto.
- Assunto: `[<Loja>] <título> — <data>`; corpo: título, tipo, data/hora, local, link para `/agenda/`.

## Scheduler

- App `agenda` com management command `agenda_lembretes`:
  1. Busca eventos com `data_hora` dentro da janela de 49h/25h e `lembrete_XX_enviado_em IS NULL`.
  2. Dentro da janela, envia somente nos ticks cujo horário local é 07:00 (tolerância do loop de 10 min), grava `lembrete_XX_enviado_em`.
- Idempotência: timestamp marcado em transação com o envio—falha SMTP não marca (retenta no próximo tick válido); após passar a janela desiste e loga.
- Serviço novo no `docker-compose.yml`: container `agenda-cron` loop `while true; run; sleep 300`, `restart: unless-stopped`.

## Fora de escopo (proposta)

- Importar histórico de eventos do sistema antigo.
- Confirmação de presença pelo membro (responder e-mail/clique).
- Integração OAuth por usuário no Google (individual).
- Notificações além dos dois lembretes.

## Critérios de aceitação

1. Tesoureiro e viewer não veem botões de criar/editar/excluir/presença e recebem 403 em POST direto a essas rotas; demais perfis conseguem.
2. Evento criado aparece em `/agenda/` filtrado pelo tenant; badges com a cor do tipo.
3. Após a `data_hora`, secretário registra presenças de membros da loja; unique(evento, membro) impede duplicação; justificativa obrigatória visível quando JUSTIFICADO.
4. Execução do command duas vezes na mesma janela não duplica e-mails (timestamps marcados).
5. Evento sincronizado guarda `google_event_id`; edição e exclusão propagem para o Google em tenant com calendar configurado.
6. Emails partem às 07:00 de D-2 e D-1 para membros ativos com e-mail; membros sem e-mail são pulados com log.
7. Sem `GOOGLE_CALENDAR_ID`, o botão de sync não aparece e o restante da agenda funciona normalmente.
