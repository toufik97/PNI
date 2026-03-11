from django.urls import path

from . import views

app_name = 'vaccines'

urlpatterns = [
    path('settings/product/new/', views.product_create, name='product_create'),
    path('settings/product/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('settings/product/<int:pk>/delete/', views.product_delete, name='product_delete'),

    path('settings/series/new/', views.series_create, name='series_create'),
    path('settings/series/<int:pk>/edit/', views.series_edit, name='series_edit'),
    path('settings/series/<int:pk>/delete/', views.series_delete, name='series_delete'),

    path('settings/vaccine/new/', views.vaccine_create, name='vaccine_create'),
    path('settings/vaccine/<int:pk>/edit/', views.vaccine_edit, name='vaccine_edit'),
    path('settings/vaccine/<int:pk>/delete/', views.vaccine_delete, name='vaccine_delete'),

    path('settings/group/new/', views.group_create, name='group_create'),
    path('settings/group/<int:pk>/edit/', views.group_edit, name='group_edit'),
    path('settings/group/<int:pk>/delete/', views.group_delete, name='group_delete'),

    path('settings/', views.vaccine_settings, name='settings'),
    path('settings/<str:tab>/', views.vaccine_settings, name='settings_tab'),
]
