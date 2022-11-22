from django.contrib import admin
from django.urls import path
from ninja import NinjaAPI
from epicpy import Wallet, Node


api = NinjaAPI()


@api.get("/add")
def add(request):
    wallet = Wallet(secret=r'C:\Users\blacktyger\.epic\main\.owner_api_secret')
    wallet.open_wallet(password='majkut11')

    tx = wallet.send_transaction(method='http', amount=0.077,
                                 message="https://GiverOfEpic.epic.tech",
                                 address="http://209.127.178.120:34615")

    return {"result": tx}


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    ]
