from django.urls import path

from tarefas import views

app_name = 'tarefas'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('<int:pk>/editar/', views.editar, name='editar'),
    path('<int:pk>/concluir/', views.concluir, name='concluir'),
    path('<int:pk>/reabrir/', views.reabrir, name='reabrir'),
    path('<int:pk>/excluir/', views.excluir, name='excluir'),
    path('contato/<int:contato_id>/nova/', views.nova_para_contato, name='nova_para_contato'),
]
