from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('vaccines/', include('vaccines.urls')),
    path('', include('patients.urls')),
]
