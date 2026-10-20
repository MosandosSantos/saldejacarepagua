# Spec: 001 — Problema Autenticação

**Criada**: 2026-10-02 · **Fonte**: `specs/legacy/code-audit-2026-10-02.md` · **Status**: Draft

## Objetivo

Endurecer o fluxo de autenticação/sessão web e eliminar os defeitos de qualidade que afetam o caminho de login e as ferramentas que o analisam.

## Problemas com evidência

| # | Problema | Evidência | Severidade |
|---|----------|-----------|------------|
| A1 | BOM (U+FEFF) no início de `tarefas/views.py` quebra parsers (radon/linters) | `radon cc` → `ERROR: invalid non-printable character U+FEFF` | Média |
| A2 | Bind `0.0.0.0` em dev (`helpers.py:84`) sem guard explícito de ambiente | Bandit B104 | Baixa (dev-only) |
| A3 | Fluxo web de login sem testes: espelho `usuarios` automático, fallback Django, rate limit 5 | Não existe `test_login_web*`; só API tem (`test_auth_api.py`) | Alta |
| A4 | Rate limit em cache volátil: reinício do servidor zera contador | Implementação em cache Django (documentação) | Baixa — decisão de aceitar/documentar |
| A5 | Ciclo de convites/ativação (`convites`, token de ativação) sem teste de expiração/uso único | Ausência de teste | Média |

## Requisitos

- **RF-01**: Código-fonte sem BOM em nenhum `.py` (validável por varredura).
- **RF-02**: Bind de desenvolvimento só ocorre quando `DJANGO_DEBUG` ativo; produção nunca expõe `0.0.0.0` no código.
- **RF-03**: Suíte de testes cobre: login válido (espelho criado), login inválido, rate limit (6ª tentativa bloqueada), login de usuário só-GPRB e só-Django, `viewer` autenticado.
- **RF-04**: Testes cobrem ciclo de convite: criação → ativação → reuso bloqueado.

## Critérios de aceite

- `radon cc` analisa `tarefas/views.py` sem erro.
- Bandit não reporta B104 para caminhos de produção (guard presente).
- `pytest teste/ -k "login or ativacao"` passa com os novos testes.

## Fora de escopo

- 2FA/SSO; troca do modelo de sessão; persistência de rate limit em banco (decisão futura).
