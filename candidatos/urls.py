from django.urls import path

from candidatos import views

app_name = 'candidatos'

urlpatterns = [
    path('criar/', views.criar_candidato, name='criar_candidato'),
    path('excluir/<int:pk>/', views.excluir_candidato, name='excluir_candidato'),
    path('detalhe/<int:pk>/', views.candidato_detalhe, name='detalhe'),
    path('api/modal-detalhe/<int:pk>/', views.candidato_modal_detalhe, name='api_modal_detalhe'),
    path('api/aprovar/<int:pk>/', views.candidato_aprovar, name='api_aprovar'),
    path('api/aprovar-encaminhar/<int:pk>/', views.candidato_aprovar_encaminhar, name='api_aprovar_encaminhar'),
    path('api/devolver/<int:pk>/', views.candidato_devolver, name='api_devolver'),
    path('api/prefeituras/', views.api_prefeituras, name='api_prefeituras'),
    path('api/lojas/', views.api_lojas_por_prefeitura, name='api_lojas_por_prefeitura'),
    path('portal/<str:token>/', views.candidato_dashboard, name='portal_dashboard'),
    path('portal/<str:token>/suplica/', views.candidato_suplica, name='portal_suplica'),
    path('portal/<str:token>/definir-senha/', views.candidato_definir_senha, name='portal_definir_senha'),
    path('<str:token>/', views.candidato_formulario, name='formulario'),
    path('<str:token>/definir-senha/', views.candidato_definir_senha, name='definir_senha'),
]
