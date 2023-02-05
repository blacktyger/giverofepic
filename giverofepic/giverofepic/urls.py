from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from wallet.api import api as wallet_api
from website import views as website_views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/wallet/", wallet_api.urls),
    ]

urlpatterns += [
    path('', website_views.HomeView.as_view(), name='home'),
    path('django-rq/', include('django_rq.urls'))
    ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
