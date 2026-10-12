"""Rotas web da agenda (namespace 'agenda')."""
from django.urls import path

from . import views

app_name = 'agenda'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('novo/', views.novo, name='novo'),
    path('<int:id>/editar/', views.editar, name='editar'),
    path('<int:id>/excluir/', views.excluir, name='excluir'),
    path('<int:id>/presenca/', views.presenca, name='presenca'),
    path('<int:id>/presenca/salvar/', views.presenca_salvar, name='presenca_salvar'),
    path('<int:id>/google/', views.google_sync_view, name='google_sync'),
]
