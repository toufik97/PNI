from django.urls import path
from . import views

app_name = 'vaccines'

urlpatterns = [
    # Vaccine CRUD — must come before the catch-all tab route
    path('settings/vaccine/new/', views.vaccine_create, name='vaccine_create'),
    path('settings/vaccine/<int:pk>/edit/', views.vaccine_edit, name='vaccine_edit'),
    path('settings/vaccine/<int:pk>/delete/', views.vaccine_delete, name='vaccine_delete'),

    # Group CRUD
    path('settings/group/new/', views.group_create, name='group_create'),
    path('settings/group/<int:pk>/edit/', views.group_edit, name='group_edit'),
    path('settings/group/<int:pk>/delete/', views.group_delete, name='group_delete'),

    # Main settings page (with optional tab)
    path('settings/', views.vaccine_settings, name='settings'),
    path('settings/<str:tab>/', views.vaccine_settings, name='settings_tab'),
]
