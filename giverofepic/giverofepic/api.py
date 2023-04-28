from django.contrib.admin.views.decorators import staff_member_required
from ninja import NinjaAPI

from wallet.api import api as wallet
from giveaway.api import api as giveaway

api = NinjaAPI(docs_decorator=staff_member_required)

api.add_router("/wallet/", wallet)
api.add_router("/giveaway/", giveaway)
