from django.urls import path

from campanhas import views

app_name = 'campanhas'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('ads/', views.em_breve, {'secao': 'ads'}, name='ads'),
    path('instagram/', views.em_breve, {'secao': 'instagram'}, name='instagram'),
    path('criativos/', views.em_breve, {'secao': 'criativos'}, name='criativos'),
    path('novo/', views.novo, name='novo'),
    path('<int:pk>/', views.detalhe, name='detalhe'),
    path('<int:pk>/editar/', views.editar, name='editar'),
    path('<int:pk>/excluir/', views.excluir, name='excluir'),
]
