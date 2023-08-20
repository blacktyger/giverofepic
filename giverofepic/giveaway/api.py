from ninja import Router

from giverofepic.settings import CLAIM_LINK_API_KEYS
from wallet.default_settings import ERROR, SUCCESS
from giverofepic.tools import CustomAPIKeyAuth
from wallet.epic_sdk import utils
from giveaway.models import Link
from .schema import LinkSchema


api = Router()
auth = CustomAPIKeyAuth()
logger = utils.get_logger()


"""API ENDPOINTS"""
# @api.post("/generate_links")
# def generate_links(request, payload: LinkSchema):
#     """ Generate a link for wallet transaction
#     :param request:
#     :param payload: link args
#     :return:
#     """
#
#     if payload.api_key not in CLAIM_LINK_API_KEYS:
#         return utils.response(ERROR, 'invalid apikey')
#
#     if payload.personal and not payload.address:
#         return utils.response(ERROR, 'personal link needs receiver address')
#
#     if not payload.personal and payload.address:
#         logger.warning('in blanco link does not require address')
#         payload.address = 'example_address'
#
#     link = Link.objects.create(**payload.dict())
#     link.register()
#     return utils.response(SUCCESS, 'link successfully generated', link.ready_url)


# @api.post("/get_link", auth=auth)
# def generate_link(request, payload: LinkSchema):
#     # payload.issuer_api_key = SecureRequest(request).secret_key
#     print(payload)
#
#     if not payload.issuer_api_key:
#         return utils.response(ERROR, 'invalid apikey')
#
#     link = Link.objects.create(**payload.dict())
#     print(link.get_url())
#
#     Link.validate_short_link()

