from django.urls import path

from funil import views

app_name = 'funil'

urlpatterns = [
    path('', views.kanban, name='kanban'),
    path('novo-lead/', views.novo_lead, name='novo_lead'),
    path('nova-atividade/', views.nova_atividade, name='nova_atividade'),
    path('importar/', views.importar_leads, name='importar_leads'),
    path('<int:pk>/mover/', views.mover, name='mover'),
]