"""Views do Funil (kanban) — organizadas por responsabilidade (SRP).

Extraindo o monolito recepcao/views.py (602 linhas) em modulos focados:
  - helpers: funcoes auxiliares compartilhadas
  - kanban: renderizacao do quadro + mover + excluir
  - leads: cadastro rapido de lead
  - importacao: importacao de CSV
  - board: contagens e dados do board (para AJAX/drag)
  - atividades: criacao de tarefas

Para usar nas urls.py:
  from recepcao.views import kanban, leads, importacao, board, atividades
"""
