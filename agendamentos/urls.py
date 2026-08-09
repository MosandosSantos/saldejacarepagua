from django.urls import path

from agendamentos import views

app_name = 'agendamentos'

urlpatterns = [
    path('', views.agenda, name='agenda'),
]