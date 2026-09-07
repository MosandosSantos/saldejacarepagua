from django.urls import path

from acesso import views

app_name = 'acesso'

urlpatterns = [
    path('', views.login_web, name='login'),
    path('onboarding/', views.onboarding, name='onboarding'),
    path('logout/', views.logout_web, name='logout'),
]
