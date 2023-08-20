from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from giverofepic.api import api
from website import views as website_views
from giveaway import views as giveaway_views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),

    ]

urlpatterns += [
    path('', website_views.HomeView.as_view(), name='home'),
    path('django-rq/', include('django_rq.urls')),
    path('claim/<code>', giveaway_views.ClaimLinkView.as_view(), name='giveaway'),
    path('giveaway/<code>', giveaway_views.ClaimLinkView.as_view(), name='giveaway'),
    path('claim/', giveaway_views.ClaimLinkView.as_view(), name='giveaway'),
    path('qr_code/', include('qr_code.urls', namespace="qr_code")),
    ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
