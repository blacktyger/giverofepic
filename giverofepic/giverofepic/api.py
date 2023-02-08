from ninja import NinjaAPI

from wallet.api import api as wallet
from giveaway.api import api as giveaway
from integrations.api import api as integrations

api = NinjaAPI()

api.add_router("/wallet/", wallet)
api.add_router("/giveaway/", giveaway)
api.add_router("/integrations/", integrations)
