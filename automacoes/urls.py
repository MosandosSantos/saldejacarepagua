from django.urls import path

from automacoes import views

app_name = 'automacoes'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('nova/', views.nova, name='nova'),
    path('<int:pk>/editar/', views.editar, name='editar'),
    path('<int:pk>/ativar/', views.ativar, name='ativar'),
    path('<int:pk>/duplicar/', views.duplicar, name='duplicar'),
    path('<int:pk>/excluir/', views.excluir, name='excluir'),
    path('<int:pk>/testar/', views.testar, name='testar'),
    path('estagnadas/', views.estagnadas, name='estagnadas'),
]
