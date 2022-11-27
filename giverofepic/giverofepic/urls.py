from django.contrib import admin
from django.urls import path, include
from wallet.api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    ]

urlpatterns += [
    path('django-rq/', include('django_rq.urls'))
]
