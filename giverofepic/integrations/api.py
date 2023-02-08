import http

from ninja import Router

from integrations.models import FormResult
from integrations.schema import PayloadSchema
from wallet.epic_sdk.utils import get_logger

api = Router()
logger = get_logger()


"""API ENDPOINTS"""
@api.get("/form_result")
def generate_link(request):
    return http.HTTPStatus.OK


@api.post("/form_result")
def generate_link(request, payload: PayloadSchema):
    try:
        form = FormResult.from_body(payload.dict())
        logger.info(f">> Received new form and saved in db, {form}")
    except Exception as e:
        logger.error(e)

    return http.HTTPStatus.ACCEPTED
