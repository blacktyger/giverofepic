from ninja import NinjaAPI

from wallet.api import api as wallet
from giveaway.api import api as giveaway

api = NinjaAPI()

api.add_router("/wallet/", wallet)
api.add_router("/giveaway/", giveaway)
