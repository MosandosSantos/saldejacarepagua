# Design: Consolidar Agenda em Tarefas

**Data:** 2026-08-09
**Status:** Aprovado
**Decisão-chave:** descartar 100% da Agenda (app, tabela, API, Node legado, SQL, testes, docs) e portar apenas o recurso `hora` para `Tarefa`.

## Contexto

O CRM tinha dois conceitos sobrepostos:

- **Agenda (`agendamentos`)** — espelho somente-leitura da tabela `agendamentos` do banco legado `esferacrm`. Tinha `hora`, `offset_dias` (cálculo de dia útil), `tipo`/`tipo_label`. Sem CRUD na web; dados vinham de fora.
- **Tarefas (`tarefas`)** — CRUD completo, prioridade, responsável, lembretes (atrasadas/hoje/próximas), badge, escopo por tenant, criar a partir do contato.

Ambos agrupavam itens por dia para a mesma pergunta ("o que faço hoje?"). `esferacrm` foi confirmado como legado morto — nenhum código de produção cria `Agendamento`, apenas testes.

## Objetivo

Manter só **Tarefas** no menu, incorporando o único recurso de Agenda genuinamente ausente: **horário do dia (`hora`)**. Descartar todo o resto da Agenda.

## Fora de escopo (YAGNI)

- Portar `offset_dias` / cálculo de dia útil — é lógica de *quem gera* o item (automação), não do item.
- Portar `tipo`/`tipo_label` — `prioridade` já cobre categorização.
- Migrar linhas existentes de `Agendamento` para `Tarefa` — dados legados descartados.

## Mudanças

### 1. Modelo `Tarefa` — adicionar `hora`

```python
hora = models.TimeField(null=True, blank=True)
```

- Opcional. Tarefa sem `hora` continua válida (lembrete por data).
- `Meta.ordering`: `['concluida', 'vencimento', 'hora', 'id']` — mesmo dia ordena por horário; nulos agrupam.
- Nenhum outro campo do modelo muda.

### 2. Views `tarefas/views.py`

- `_decorar(t)`: incluir `'hora': t.hora`.
- Novo `_parse_hora(raw, erros)`: aceita `HH:MM`, retorna `None` se vazio, anexa erro se inválido (espelha `_parse_vencimento`).
- `lista` (POST `criar`), `editar` (POST), `nova_para_contato`: leem e persistem `hora`.

### 3. Templates `tarefas`

- `lista.html`: input `<input type="time" name="hora">` no form rápido do topo; exibir "HH:MM" ao lado do título quando houver.
- `editar.html`: input `hora`.
- `partials/_linha.html`: exibir horário quando presente.

### 4. Remoção completa da Agenda

**Deletar arquivos/diretórios:**

- `agendamentos/` (app inteiro)
- `api/v1/routes/agendamentos.py`
- `api/v1/repositories/agendamento_repository.py`
- `api/v1/services/agendamento_service.py`
- `api/v1/schemas/agendamento.py`
- `teste/test_agendamentos_api.py`

**Editar (remover referências):**

| Arquivo | Remover |
|---|---|
| `core/settings.py` | `'agendamentos'` do `INSTALLED_APPS` (~L32) |
| `core/urls.py` | `path('agenda/', include(...))` → trocar por `RedirectView` 302 → `tarefas:lista` |
| `acesso/context_processors.py` | constante `_ICONE_AGENDA` (L16-18) e tupla `('Agenda', ...)` (L51) |
| `api/v1/router.py` | import `agendamentos_router` (L6) + `include_router` (L27) |
| `server.js` | bloco `/api/agendamentos` (L79-111) — Node legado |
| `index.html` | global `APPTS` (L541, 598, 601), `AGENDA_ICONS`+`renderAgenda()` (L969-994), div `#agendaWrap` |
| `init-db.sql` | `CREATE TABLE agendamentos` (L27), seed `INSERT` (L69-72), count do stats (L87) |
| `aula4.sql` | 3 `UPDATE agendamentos` (L49-51) |
| `teste/test_fase_k_timestamps.py` | `'agendamentos'` da lista (L36) |
| `DOCS/api.md` | linhas L68, L87 |
| `systemdesign.md` | linha L215 |

### 5. Banco — migrations (no app `tarefas`)

1. `00XX_tarefa_hora.py` — `AddField hora` (gerado por `makemigrations`).
2. `00XX_drop_agendamentos.py` — `RunSQL`:
   - `DROP TABLE IF EXISTS agendamentos;`
   - `DELETE FROM django_migrations WHERE app='agendamentos';`

Sem FK reverso a tratar — nenhum modelo referencia `Agendamento`.

### 6. Redirect de bookmark

`/agenda/` → 302 `/tarefas/` (`RedirectView`, `permanent=False`) para bookmarks antigos não quebrarem.

### 7. Testes

- **Deletar:** todos os testes de agendamentos (vão com o app e `teste/test_agendamentos_api.py`).
- **Adicionar em `tarefas/tests.py`:**
  - criar tarefa com `hora` válida;
  - ordenação por `hora` dentro do mesmo `vencimento`;
  - rejeitar `hora` inválida (erro no form);
  - `hora` opcional (`None` é válido).

## Verificação

1. `python manage.py makemigrations tarefas` → gera migration de `hora`.
2. `python manage.py migrate` → aplica `hora` + drop da tabela `agendamentos`.
3. `python manage.py test` (ou `pytest`) → tudo verde.
4. `grep -ri agendamento .` no código → retorna vazio (exceto histórico git).
5. Navegar em `/agenda/` → redireciona para `/tarefas/`.

## Riscos

- **Tabela `agendamentos` gerenciada por dois lugares** (`init-db.sql` e migrations do app): o `DROP TABLE IF EXISTS` é idempotente e cobre ambos.
- **`django_migrations` órfão**: limpo pelo `DELETE` na mesma migration de drop.
- **`index.html` legado**: perde o widget de agenda, mas só Django é o app vivo — aceito.
