from django.urls import path

from recepcao.views import (
    atividades,
    board,
    importacao,
    kanban,
    leads,
)

app_name = 'recepcao'

urlpatterns = [
    path('', kanban.kanban, name='kanban'),
    path('novo-lead/', leads.novo_lead, name='novo_lead'),
    path('nova-atividade/', atividades.nova_atividade, name='nova_atividade'),
    path('importar/', importacao.importar_leads, name='importar_leads'),
    path('<int:pk>/mover/', kanban.mover, name='mover'),
    path('<int:pk>/excluir/', kanban.excluir_negocio, name='excluir_negocio'),
]
