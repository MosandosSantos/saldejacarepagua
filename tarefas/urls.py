from django.urls import path

from tarefas import views

app_name = 'tarefas'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('ranking/', views.ranking, name='ranking'),
    path('eventos/json/', views.eventos_json, name='eventos_json'),
    path('eventos/criar/', views.evento_criar, name='evento_criar'),
    path('eventos/<int:evento_id>/editar/', views.evento_editar, name='evento_editar'),
    path('eventos/<int:evento_id>/excluir/', views.evento_excluir, name='evento_excluir'),
    path('<int:pk>/editar/', views.editar, name='editar'),
    path('<int:pk>/concluir/', views.concluir, name='concluir'),
    path('<int:pk>/reabrir/', views.reabrir, name='reabrir'),
    path('<int:pk>/excluir/', views.excluir, name='excluir'),
    path('contato/<int:contato_id>/nova/', views.nova_para_contato, name='nova_para_contato'),
    path('exportar/', views.exportar_ics, name='exportar_ics'),
    path('ranking/exportar/', views.exportar_calendario_ics, name='exportar_calendario_ics'),
    path('importar/', views.importar_ics, name='importar_ics'),
]
