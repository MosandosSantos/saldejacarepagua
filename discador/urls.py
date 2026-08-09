from django.urls import path

from discador import views

app_name = 'discador'

urlpatterns = [
    path('', views.operador, name='operador'),
    path('filas/', views.filas, name='filas'),
    path('filas/nova/', views.fila_form, name='fila_nova'),
    path('filas/<int:pk>/editar/', views.fila_form, name='fila_editar'),
    path('filas/<int:pk>/excluir/', views.fila_excluir, name='fila_excluir'),
    path('fila/<int:fila_id>/chamar/', views.chamar, name='chamar'),
    path('chamadas/<int:pk>/resultado/', views.registrar_resultado, name='registrar_resultado'),
    path('scripts/', views.scripts, name='scripts'),
    path('scripts/nova/', views.script_form, name='script_nova'),
    path('scripts/<int:pk>/editar/', views.script_form, name='script_editar'),
    path('scripts/<int:pk>/excluir/', views.script_excluir, name='script_excluir'),
]
