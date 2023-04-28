from ninja import Router

from giverofepic.tools import CustomAPIKeyAuth, SecureRequest
from wallet.default_settings import ERROR, SUCCESS
from wallet.epic_sdk import utils
from giveaway.models import Link
from .schema import LinkSchema


api = Router()
auth = CustomAPIKeyAuth()
logger = utils.get_logger()


"""API ENDPOINTS"""
@api.post("/generate_link", auth=auth)
def generate_link(request, payload: LinkSchema):
    """ Generate a link for wallet transaction
    :param request:
    :param payload: link args
    :return:
    """
    # Get API_KEY from headers and save to payload
    payload.issuer_api_key = SecureRequest(request).secret_key
    print(payload)

    # TODO: Uncomment for production
    # if not payload.issuer_api_key:
    #     return utils.response(ERROR, 'invalid apikey')

    if payload.personal and not payload.address:
        return utils.response(ERROR, 'personal link needs receiver address')

    if not payload.personal and payload.address:
        logger.warning('in blanco link does not require address')
        payload.address = 'example_address'

    link = Link.objects.create(**payload.dict())
    return utils.response(SUCCESS, 'link successfully generated', link.get_url())


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

