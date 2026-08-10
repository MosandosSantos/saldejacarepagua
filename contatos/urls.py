from django.urls import path

from contatos import views

app_name = 'contatos'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('leads-pobres/', views.leads_pobres, name='leads_pobres'),
    path('importar/', views.importar, name='importar'),
    path('importar/modelo/', views.baixar_modelo, name='modelo'),
    path('exportar/', views.exportar_csv, name='exportar'),
    path('exportar/negocios/', views.exportar_negocios_csv, name='exportar_negocios'),
    path('carteiras/', views.carteiras, name='carteiras'),
    path('carteiras/<int:pk>/', views.carteira_detalhe, name='carteira_detalhe'),
    path('campos/', views.campos_personalizados, name='campos'),
    path('campos/<int:pk>/editar/', views.editar_campo, name='editar_campo'),
    path('campos/<int:pk>/excluir/', views.excluir_campo, name='excluir_campo'),
    path('novo/', views.novo, name='novo'),
    path('<int:pk>/', views.detalhe, name='detalhe'),
    path('<int:pk>/editar/', views.editar, name='editar'),
    path('<int:pk>/excluir/', views.excluir, name='excluir'),
    path('<int:pk>/negocios/novo/', views.negocio_novo, name='negocio_novo'),
    path('<int:pk>/negocios/<int:negocio_id>/editar/', views.negocio_editar, name='negocio_editar'),
    path('<int:pk>/negocios/<int:negocio_id>/orcamento/', views.orcamento_pdf, name='orcamento_pdf'),
    path('<int:pk>/negocios/<int:negocio_id>/excluir/', views.negocio_excluir, name='negocio_excluir'),
    path('<int:pk>/negocios/<int:negocio_id>/principal/', views.negocio_tornar_principal, name='negocio_tornar_principal'),
    path('<int:pk>/notas/', views.adicionar_nota, name='adicionar_nota'),
    path('<int:pk>/notas/<int:nota_id>/excluir/', views.excluir_nota, name='excluir_nota'),
    path('<int:pk>/tags/', views.adicionar_tag, name='adicionar_tag'),
    path('<int:pk>/tags/<int:tag_id>/remover/', views.remover_tag, name='remover_tag'),
]