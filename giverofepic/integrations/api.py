import http

from ninja import Router

from integrations.models import FormResult, FormUser
from wallet.default_settings import QUIZ_API_KEY
from integrations.schema import FormResultSchema
from wallet.epic_sdk.utils import get_logger
from giveaway.models import Link


api = Router()
logger = get_logger()


"""API ENDPOINTS"""
@api.post("/form_webhook")
def form_webhook(request, payload: FormResultSchema):
    """POST endpoint as webhook, receive form results and store them in db"""
    if payload.form:
        try:
            payload = payload.dict()
            payload['user'] = FormUser.from_body(payload)

            if not payload['user'].is_locked():
                form = FormResult.from_body(payload)
                print(form, form.user)

                if form:
                    logger.info(f">> Received new {form} from {form.user}")

                    # Creates new Link object for claiming the reward
                    Link.objects.create(
                        issuer_api_key=QUIZ_API_KEY,
                        reusable=0,
                        personal=False,
                        currency='EPIC',
                        claimed=False,
                        expires=form.get_expire_date(),
                        amount=form.reward,
                        event='quiz',
                        code=form.session_id
                        ).get_url()
            else:
                form = FormResult.from_body(payload)
                form.is_valid = False
                form.save()

        except Exception as e:
            logger.error(f">> Form webhook fail, {e}")

    return http.HTTPStatus.ACCEPTED


# @api.get("/form_webhook")
# def form_webhook():
#     """GET endpoint for health checks from forms.app"""
#     return http.HTTPStatus.OK
