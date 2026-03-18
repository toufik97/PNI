from django.urls import path

from . import views
from . import scenario_views

app_name = 'vaccines'

urlpatterns = [
    path('settings/product/new/', views.product_create, name='product_create'),
    path('settings/product/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('settings/product/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('settings/product/<int:pk>/toggle/', views.product_toggle_active, name='product_toggle_active'),

    path('settings/policy-version/new/', views.policy_version_create, name='policy_version_create'),
    path('settings/policy-version/<int:pk>/edit/', views.policy_version_edit, name='policy_version_edit'),
    path('settings/policy-version/<int:pk>/delete/', views.policy_version_delete, name='policy_version_delete'),

    path('settings/series/new/', views.series_create, name='series_create'),
    path('settings/series/<int:pk>/edit/', views.series_edit, name='series_edit'),
    path('settings/series/<int:pk>/delete/', views.series_delete, name='series_delete'),

    path('settings/dependency/new/', views.dependency_create, name='dependency_create'),
    path('settings/dependency/<int:pk>/edit/', views.dependency_edit, name='dependency_edit'),
    path('settings/dependency/<int:pk>/delete/', views.dependency_delete, name='dependency_delete'),

    path('settings/global-constraint/new/', views.global_constraint_create, name='global_constraint_create'),
    path('settings/global-constraint/<int:pk>/edit/', views.global_constraint_edit, name='global_constraint_edit'),
    path('settings/global-constraint/<int:pk>/delete/', views.global_constraint_delete, name='global_constraint_delete'),
    
    path('settings/policy/export/', views.policy_export, name='policy_export'),
    path('settings/policy/import/', views.policy_import, name='policy_import'),

    # Scenario Simulator
    path('settings/scenario/new/', scenario_views.scenario_create, name='scenario_create'),
    path('settings/scenario/<int:pk>/edit/', scenario_views.scenario_edit, name='scenario_edit'),
    path('settings/scenario/<int:pk>/delete/', scenario_views.scenario_delete, name='scenario_delete'),
    path('settings/scenario/<int:pk>/run/', scenario_views.scenario_run, name='scenario_run'),
    path('settings/scenarios/run-all/', scenario_views.scenario_run_all, name='scenario_run_all'),
    path('settings/scenarios/export/', scenario_views.scenario_export, name='scenario_export'),
    path('settings/scenarios/import/', scenario_views.scenario_import, name='scenario_import'),

    path('settings/', views.vaccine_settings, name='settings'),
    path('settings/<str:tab>/', views.vaccine_settings, name='settings_tab'),
]
