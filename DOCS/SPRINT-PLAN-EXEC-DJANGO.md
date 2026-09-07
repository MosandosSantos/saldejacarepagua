# Execução — Sprints 7/8/9 (Candidatos + Portal Súplica + Presença + Financeiro)

## Hipóteses de paralelo

| Função candidato | Hipótese / risco |
|---|---|
| Portal `candidato/<token>` | já funciona com token + senha + uploads |
| Aprovação final (PRIOR + GRAO_MESTRE + SYS_ADMIN) | prefeito, grande_tesoureiro, grande_chanceler podem aprovar; SYS_ADMIN bypass total |
| Iniciação → Member | `create_member_from_candidato` ainda não existe; vai no Sprint 9 |
| Observações (autor + papel + texto) | a view `encaminhar_view` recebe `observacao` via POST |
| E-mail de convite | envia com logo URL absoluto; usa template `candidatos/email_convite.html` |

## PS: código limpo mantido

- views usam `web_login_required` + `web_requer_edicao`.
- service layer `candidatos/oficialato.py` isolado do HTTP.
- urls separados por responsabilidade; `candidatos/urls.py` exporta apenas as views públicas + views de workflow.
- middleware de sessão valida usuário a cada request; `pode_editar` é a porta de entrada da edição.

## Próximos passos

1. Validar `candidatos/oficialato.py` com testes focados: `sys_admin` bypass; `prefeito` avança 1 nível; `teste` só recua quando pode.
2. Implementar `Candidato.objects.create_member_from_candidato` (Sprint 9); transformar EM_REVISAO/APROVADO → Member + User vinculado.
3. Presença: `Meeting` + `Attendance` views com `SESSION_NOT_HAPPENED_YET` e upsert em lote.
4. Financeiro: `Categoria` + `Lancamento` (ABERTO/PARCIAL/PAGO/ATRASADO/PREVISTO) com serviço de status calculado.
