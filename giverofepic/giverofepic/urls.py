from django.contrib import admin
from django.urls import path
from ninja import NinjaAPI


api = NinjaAPI()


@api.get("/add")
def add(request):
    return


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    ]
