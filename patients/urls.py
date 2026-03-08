from django.urls import path
from . import views

app_name = 'patients'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('register/', views.register, name='register'),
    path('child/<str:child_id>/', views.profile, name='profile'),
    path('child/<str:child_id>/record/', views.record_dose, name='record_dose'),
]
