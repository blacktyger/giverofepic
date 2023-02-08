import http

from ninja import Router

from integrations.schema import FormResultSchema
from wallet.epic_sdk.utils import get_logger
from integrations.models import FormResult

api = Router()
logger = get_logger()


"""API ENDPOINTS"""
@api.get("/form_webhook")
def form_webhook(request):
    """GET endpoint for health checks from forms.app"""
    return http.HTTPStatus.OK


@api.post("/form_webhook")
def form_webhook(request, payload: FormResultSchema):
    """POST endpoint as webhook, receive form results and store them in db"""
    try:
        form = FormResult.from_body(payload.dict())
        logger.info(f">> Received new form and saved in db, {form}")
    except Exception as e:
        logger.error(f">> Form\Result webhook fail, {e}")

    return http.HTTPStatus.ACCEPTED
