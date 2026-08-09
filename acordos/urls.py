from django.urls import path

from acordos import views

app_name = 'acordos'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('simular/', views.simular, name='simular'),
    path('contato/<int:contato_id>/simular/', views.simular, name='simular_contato'),
    path('contato/<int:contato_id>/registrar/', views.registrar, name='registrar'),
    path('<int:pk>/', views.detalhe, name='detalhe'),
    path('<int:pk>/pago/', views.marcar_pago, name='marcar_pago'),
    path('<int:pk>/recusar/', views.recusar, name='recusar'),
]
