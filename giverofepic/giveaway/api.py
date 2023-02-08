from ninja import Router

from faucet.models import SecureRequest
from giveaway.models import Link
from giverofepic.tools import CustomAPIKeyAuth
from wallet.default_settings import ERROR
from wallet.epic_sdk import utils
from wallet.epic_sdk.utils import get_logger
from giverofepic.schema import LinkSchema


api = Router()
auth = CustomAPIKeyAuth()
logger = get_logger()


"""API ENDPOINTS"""
@api.post("/generate_link", auth=auth)
def generate_link(request, payload: LinkSchema):
    payload.issuer_api_key = SecureRequest(request).secret_key
    print(payload)
    if not payload.issuer_api_key:
        return utils.response(ERROR, 'invalid apikey')

    from cryptography.fernet import Fernet

    key = Fernet.generate_key()
    f = Fernet(key)
    token = f.encrypt(b"esZ7pubuHN4Dyn8WsCRjzhe12ZtgHqmnthGoopA1iSskm2xwXcKK")
    print(token)
    # object = Code.objects.create(**payload.dict())
    # print(object.get_short_link())

