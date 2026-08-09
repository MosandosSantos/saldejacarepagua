from django.urls import path

from funil import views

app_name = 'funil'

urlpatterns = [
    path('', views.kanban, name='kanban'),
    path('<int:pk>/mover/', views.mover, name='mover'),
]