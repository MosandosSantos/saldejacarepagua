from django.urls import path

from acesso import views

app_name = 'acesso'

urlpatterns = [
    path('', views.login_web, name='login'),
    path('agenda/exportar/', views.exportar_agenda_publica, name='exportar_agenda_publica'),
    path('logout/', views.logout_web, name='logout'),
    path('tenant-contexto/', views.selecionar_tenant_contexto, name='selecionar_tenant_contexto'),
]
