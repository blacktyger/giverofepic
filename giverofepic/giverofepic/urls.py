from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from giveaway import views as giveaway_views
from giverofepic.api import api as project_api
from website import views as website_views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", project_api.urls),

    ]

urlpatterns += [
    path('', website_views.HomeView.as_view(), name='home'),
    path('claim/<code>', giveaway_views.ClaimLinkView.as_view(), name='giveaway'),
    path('django-rq/', include('django_rq.urls'))
    ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
