# Testes — estado atual (legado/atual)

## Comandos

```bash
# Suíte completa
python -m pytest teste/ -v

# Com cobertura
python -m pytest teste/ --cov=. --cov-report=term-missing

# Complexidade ciclomática (recepcao)
python -m radon cc recepcao/ -s
```

Runner: **pytest**, arquivos em `teste/` (41 arquivos), fixtures em `teste/conftest.py`.

## O que existe

### Testes de fases (herdados do CRM de vendas)
`test_fase_a_funil.py`, `test_fase_b_config.py`, `test_fase_d_seguranca.py`, `test_fase_e_export_email.py`, `test_fase_f_pipeline.py`, `test_fase_g_tarefas.py`, `test_fase_h_captura.py`, `test_fase_i_automacoes.py`, `test_fase_r_lead_rapido.py`, `test_fase_s8_interface_seguranca.py`, `test_fase_s_candidatos.py`, `test_fase_s_relatorios.py`, `test_fase_t_oficialato.py` — cobrem funil kanban, config, segurança, export/e-mail, pipeline, tarefas, captura de leads, automações, candidatos, relatórios, oficialato.

### Testes de API e RBAC
`test_auth_api.py` (login JWT), `test_contatos_api.py`, `test_rbac_api.py` (papéis), `test_viewer.py` (somente leitura).

### Testes de views web
`test_ativacao_web.py`, `test_atividades_view.py`, `test_kanban_views.py`, `test_kanban_prefeitura.py`, `test_leads_view.py`, `test_equipe.py`, `test_comunicacao.py`, `test_dashboard_avancado.py`, `test_helpers.py`.

### Testes de importação
`test_import_service.py`, `test_import_view.py`, `test_importador.py`, `test_lead_service.py`.

### Outros
`test_campos_personalizados.py`, `test_cache_invalidation.py`.

## Validação E2E manual (sessão de migração 02/10/2026)

Feita por curl/scripts temporários contra o banco novo `saldabritanea`:

- ✅ `healthz` → `{"status":"ok","database":"ok"}`
- ✅ Login `identifier`+`senha` → 302 → `/dashboard/`
- ✅ `/dashboard/`, `/contatos/`, `/contatos/prefeituras/`, `/contatos/lojas/`, `/contatos/financeiro/` → 200
- ✅ CRUD Potência real: POST cria (302), listar/buscar/atualizar via repositório, UPDATE sem região
- ✅ N:N membro↔lojas: POST com 2 lojas, POST sem lojas (NULL), ponte com 2 registros, filtro por loja
- ✅ Zero ocorrências de "classe"/"Regiao" no HTML renderizado

## Lacunas conhecidas (a cobrir em trabalho futuro)

1. **Sem testes automatizados para `repositories/gprb_repository.py`** — a camada GPRB (member, member_loja, prefeitura, loja) só tem validação manual.
2. N:N de lojas do membro (`definir_lojas_membro`, `lojas_do_membro`) sem teste unitário.
3. Fluxo de criação de potência/loja sem teste de integração (só manual).
4. Sem banco de teste dedicado para o modelo GPRB (testes GPRB tocarão dados se rodarem contra o banco real — usar dump ou criar `saldabritanea_test`).
5. Dashboard GPRB (rankings, BAII) sem teste — apenas smoke 200.
6. Módulos 🔶 (financeiro, automações, discador) sem cobertura do estado atual.

> Antes de rodar a suíte completa: rate limit de login (5 tentativas) pode bloquear testes repetidos — limpar cache entre execuções se necessário.
