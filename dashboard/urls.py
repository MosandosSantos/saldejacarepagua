from django.urls import path

from dashboard import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('dados/', views.dados, name='dados'),
    path('anuidade/dados/', views.anuidade_dados, name='anuidade_dados'),
]
