"""URLs do app gestao — Dashboard de Inscricoes (GEOD-CEOD)."""
from django.urls import path

from gestao import views

app_name = 'gestao'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('comunicacao/', views.comunicacoes, name='comunicacoes'),
    path('comunicacao/zap-status/', views.zap_status, name='zap_status'),
    path('comunicacao/zap-qrcode/', views.zap_qrcode, name='zap_qrcode'),
]
