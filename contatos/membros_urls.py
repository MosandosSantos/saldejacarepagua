"""Canonical URL routes for tenant-scoped member pages."""

from django.urls import path

from contatos import views

app_name = 'membros'

urlpatterns = [
    path('', views.membro_lista, name='lista'),
    path('acompanhamento/', views.acompanhamento, name='acompanhamento'),
    path('iniciacao/', views.iniciacao_graus, name='iniciacao'),
    path(
        'acompanhamento/relatorio/<str:formato>/',
        views.acompanhamento_exportar,
        name='acompanhamento_exportar',
    ),
    path('novo/', views.membro_novo, name='novo'),
    path('lojas-por-vale/', views.lojas_por_vale, name='lojas_por_vale'),
    path('<str:pk>/', views.membro_detalhe, name='detalhe'),
    path('<str:pk>/editar/', views.membro_editar, name='editar'),
    path('<str:pk>/excluir/', views.membro_excluir, name='excluir'),
    path('<str:pk>/pagamento/', views.membro_pagamento, name='pagamento'),
    path('<str:pk>/pagamento/asaas/', views.membro_pagamento_asaas, name='pagamento_asaas'),
]
