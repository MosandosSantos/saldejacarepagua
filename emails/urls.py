from django.urls import path

from emails import views

app_name = 'emails'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('novo/', views.novo, name='novo'),
    path('<int:pk>/editar/', views.editar, name='editar'),
    path('<int:pk>/excluir/', views.excluir, name='excluir'),
    path('campanha/', views.campanha, name='campanha'),
    path('enviar/<int:contato_id>/', views.enviar_contato, name='enviar_contato'),
    path('aberto/<uuid:token>/', views.rastreio_abertura, name='aberto'),
    path('clique/<uuid:token>/<str:codigo>/', views.rastreio_clique, name='clique'),
]
