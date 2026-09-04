# Code Quality Report — GPRBRCRM

**Data:** 2026-09-04 (reavaliação executada)
**Pontuação:** 73/100 (Nível 3 — Profissional)
*Nota: relatório anterior marcava 76/100 (Nível 4). A queda reflete evidências novas (LOGGING existe, mas adoção baixa; suíte com 44 falhas locais; WIP de 170+ arquivos sem commit desde 22/08).*

> **Regra do skill (cap 60):** existe issue de segurança conhecido em aberto (`allow_origins=['*']` no FastAPI) e a varredura de vulnerabilidades (bandit/pip-audit) não roda em lugar nenhum (nem local, nem CI). Se a regra do skill for aplicada literalmente, a nota formal fica **capada em 60/100** até CORS ser restringido e os scans entrarem no CI.

---

## Resumo

| Dimensão | Nota | Máx | Observação |
|----------|------|-----|------------|
| 1. Arquitetura | 8 | 10 | 11 apps bem separados + camada de serviço (`acesso/ativacao.py`, `emails/servico.py`), mas `acesso/views.py` (1316 linhas) e `dashboard/views.py` (699) são God Views |
| 2. Qualidade do Código | 7 | 10 | Boa nomenclatura; duplicações (mensagens de erro sem/pontos acento em `tarefas/views.py`, SVGs inline) |
| 3. Testes | 11 | 15 | 458 testes em 26 arquivos; 414 passam local; 44 falham (maioria ambientais — GPRB/Postgres ausente); sem cobertura configurada |
| 4. Segurança | 13 | 15 | CSRF, rate limit, sessão validada, AES-256-GCM, headers. `allow_origins=['*']` no FastAPI; sem bandit/pip-audit |
| 5. Manutenibilidade | 6 | 10 | 170+ arquivos alterados **sem commit** desde 22/08; requirements com ranges sem lock file; sem lint/type check no fluxo |
| 6. Documentação | 4 | 5 | README + DOCS/ extensos (PRDs, architecture, security); sem CHANGELOG |
| 7. Performance | 7 | 10 | select_related/prefetch em 35 pontos; CACHES (Redis opcional); dashboard ainda sem cache de KPIs; `core/gprb.py` abre conexão por função |
| 8. DevOps/CI-CD | 7 | 10 | GitHub Actions (check, migrações, pytest com Postgres), Railway + Dockerfile + Procfile; sem lint/segurança no CI; WIP sem commits |
| 9. Observabilidade | 3 | 5 | `LOGGING` configurado no settings (console INFO debug + file WARNING), mas só 5/190 módulos usam `logging`; 10 `except Exception:` silenciosos |
| 10. Confiabilidade | 7 | 10 | Fallbacks GPRB na equipe, healthz, fail-fast em prod; falhas silenciosas no dashboard; backup/DR não documentado |
| **TOTAL** | **73** | **100** | **Nível 3 — Profissional** (cap em 60 pela regra do skill enquanto CORS/scans pendentes) |

---

## Verificações executadas (2026-09-04)

| Check | Resultado |
|-------|-----------|
| `python manage.py check` | ✅ limpo |
| `python manage.py makemigrations --check --dry-run` | ✅ sem migrações pendentes |
| `python -m pytest -q` | ⚠️ 414 passed, 44 failed (458 coletados) |
| Coverage (`pytest-cov`/`coverage`) | ❌ não instalado |
| `ruff check .` | ❌ não instalado |
| `bandit -r .` | ❌ não instalado |
| `pip-audit` | ❌ não instalado |

### Classificação das 44 falhas de teste

- **~30 ambientais** — `psycopg.OperationalError` ao conectar no Postgres/GPRB em `127.0.0.1:5432` (este ambiente não tem o serviço; no CI o serviço `postgres:16` cobre). Atingem `/dashboard/`, `/contatos/`, viewer, carteiras etc.
- **~10–14 reais (desatualizadas vs. working tree ou bugs reais):**
  - `test_equipe.py::test_admin_saas_sem_tenant_nao_acessa_equipe` — **asserta o comportamento antigo** (`302`); hoje (fix do dia) admin_saas sem tenant **acessa** `/equipe/` com escopo global (`200`). Teste precisa ser atualizado para o comportamento do PRD-USUARIOS-SEM-SENHA.
  - Renames de domínio: `'Avaliação agendada' != 'Consulta agendada'` (`test_fase_f_pipeline`), `'' != 'estetica'` (nicho default, `test_fase_h_captura`, `test_importador`).
  - Mensagem duplicada sem acento: `'Informe o titulo da tarefa.'` vs `'Informe o título da tarefa.'` (`test_fase_g_tarefas` espera a versão acentuada).
  - Testes de interface (design system, botão "novo contato") desatualizados pelo rebrand Contatos→Membros.
  - `test_allowed_hosts_falha_fechado_fora_do_debug` falha por falta de `DJANGO_SECRET_KEY` no ambiente (config de teste).

---

## Pontos fortes

### Segurança (13/15)
- Secrets via env, fail-fast sem `DATABASE_URL`/`PGHOST` em produção
- CSRF completo, sessão validada contra o DB a cada request (`ValidarSessaoMiddleware`)
- Rate limit (10 tentativas/5min web; API) com `DJANGO_RATE_LIMIT=0` nos testes
- SQL parameterizado, XSS mitigado (escaping + filtro `|js`), headers (CSP, HSTS, X-Frame-Options…)
- AES-256-GCM com HKDF para dados sensíveis
- Login de usuário pendente bloqueado nos 3 caminhos; logout POST-only

### Testes (11/15)
- 458 testes cobrindo auth, RBAC, multi-tenant, segurança, rate limit, ativação sem senha
- Boas fixtures compartilhadas (`conftest.py`) e `--reuse-db`
- Testes de isolamento tenant-a-tenant

### Arquitetura (8/10)
- 11 apps com responsabilidades claras; API FastAPI router→service; rotinas de ativação isoladas em `acesso/ativacao.py`
- Multi-tenant consistente (`filtro_tenant`, `_qs_escopo`)
- `contatos/views/` fatiado

### Confiabilidade (7/10)
- Fallback local quando o GPRB cai (equipe, opções de filtro)
- Healthcheck `/healthz/`, Procfile com release (migrate), fail-closed

---

## Problemas Críticos

1. **Segurança em aberto (cap de 60):** CORS `allow_origins=['*']` (`api/main.py:35`) + **zero varredura** de dependências/vulnerabilidades (bandit, pip-audit ausentes do fluxo local e do CI).
2. **Working tree sem commits desde 22/08** — 170+ arquivos alterados (rebrand, oficialato/RER, fix da equipe). Sem checkpoint intermediário: qualquer erro destrói o histórico de "ontem" que você citou; impossível rever com `git` o estado que funcionava.
3. **Suíte desatualizada vs. working tree** — testes do HEAD referenciam labels/fluxos antigos (Consulta agendada, nicho `estetica`, "novo contato", equipe bloqueada para admin_saas). CI vai falhar até os testes acompanharem o código.
4. **Observabilidade baixa:** 5/190 módulos com `logging`; 10 `except Exception:` silenciosos (sem `logger.error`).

---

## Pontos de melhoria (priorizados)

| # | Ação | Impacto | Esforço |
|---|------|---------|---------|
| 1 | **Commitar o working tree** (ou criar branch) e manter commits pequenos por feature | Alto | Baixo |
| 2 | **Atualizar os testes desatualizados** (renames de etapa/nicho, botões do rebrand) e corrigir `test_admin_saas_sem_tenant_nao_acessa_equipe` para o novo comportamento (acesso + escopo global) | Alto | Baixo |
| 3 | **Restringir CORS** no FastAPI (allowlist por env) | Alto | Baixo |
| 4 | Instalar `bandit` + `pip-audit` e rodar no CI (job separado) | Alto | Baixo |
| 5 | Adicionar `pytest-cov` + `.coveragerc` com meta ≥60% e rodar no CI | Médio | Baixo |
| 6 | Adicionar `logging` + `logger.error(...)` nos blocos `except Exception` silenciosos (10) | Médio | Baixo |
| 7 | Unificar mensagens duplicadas (`titulo` sem acento × `título`) e extrair constantes | Baixo | Baixo |
| 8 | Cache de 60s nos KPIs do dashboard; pool de conexões no `core/gprb.py` | Médio | Médio |
| 9 | Splits dos God Views (`config()` ≈ 17 ações POST em `acesso/views.py:1316`; `dashboard/views.py:699`) | Médio | Alto |
| 10 | Adicionar ruff ao CI (lint) e CHANGELOG.md | Médio | Baixo |

---

## Comando para rodar a avaliação

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python -m pytest -q
# pendências de tooling (instalar e rodar):
pip install ruff bandit pip-audit pytest-cov
ruff check .
bandit -r . -f json -ll
pip-audit
coverage run -m pytest && coverage report --fail-under=60
```
