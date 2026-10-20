# Tarefas — Iniciação ao Grau 9

## Fase 1 — candidato ao Grau 9

- [x] **T1 — Serviço de elegibilidade**
  - RED/GREEN para grau atual 8, data do Grau 4 (> 6 meses) e presença Vale-wide ≥50%.
  - Cobrir chamadas de várias Lojas, outra tenant, ausência de chamadas e limites de data/percentual.
  - Arquivos: `contatos/iniciacao_graus.py`, `teste/test_iniciacao_graus.py`.

- [x] **T2 — View/rota autenticada**
  - Registrar `/membros/iniciacao/` e renderizar candidatos usando o escopo já empregado pelo Acompanhamento.
  - Criar o template final nesta fatia para que a view seja testada por integração.
  - Cobrir Vale ausente, tenant comum e isolamento de dados.
  - Arquivos: `contatos/views/iniciacao_graus.py`, `contatos/templates/contatos/iniciacao_graus.html`, `contatos/membros_urls.py`, `contatos/views/__init__.py`, `teste/test_iniciacao_graus.py`.

- [x] **T3 — Página e navegação**
  - Adicionar navegação sem conflitar com o Flow comercial ou Acompanhamento; matcher ativo correto.
  - Arquivos: `acesso/context_processors.py`, `teste/test_iniciacao_graus.py`.

- [x] **T4 — Verificação local**
  - Ruff, testes focados, `manage.py check`, migrations check, detector UI, build Docker e healthcheck.
  - Rodar a suíte completa uma vez e reportar o resultado/baseline sem atribuição causal não investigada.

## Próximas etapas já especificadas, ainda sem implementação

- [ ] Regras de candidatura para Graus 14, 15, 18, 19, 22, 28, 30, 31, 32 e 33, em entregas graduais após validação do Grau 9.
