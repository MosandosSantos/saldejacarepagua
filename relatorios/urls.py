from django.urls import path

from relatorios import views

app_name = 'relatorios'

urlpatterns = [
    path('', views.index, name='index'),
    path('exportar/csv/', views.exportar_csv, name='exportar_csv'),
    path('exportar/pdf/', views.exportar_pdf, name='exportar_pdf'),
]
