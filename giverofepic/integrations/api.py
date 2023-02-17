import http
from datetime import timedelta
from pprint import pprint

from django.utils import timezone
from ninja import Router

from giveaway.models import Link
from integrations.schema import FormResultSchema
from wallet.default_settings import GIVEAWAY_LINKS_LIFETIME_MINUTES, QUIZ_API_KEY
from wallet.epic_sdk.utils import get_logger
from integrations.models import FormResult, FormUser

api = Router()
logger = get_logger()

"""API ENDPOINTS"""


@api.get("/form_webhook")
def form_webhook():
    """GET endpoint for health checks from forms.app"""
    return http.HTTPStatus.OK


# e7197f0a
# aaa031ac

@api.post("/form_webhook")
def form_webhook(request, payload: FormResultSchema):
    """POST endpoint as webhook, receive form results and store them in db"""
    if payload.form:
        # try:
            payload = payload.dict()
            # print(payload)
            payload['user'] = FormUser.from_body(payload)

            if not payload['user'].is_locked():
                form = FormResult.from_body(payload)
                print(form, form.user)

                if form:
                    logger.info(f">> Received new {form} from {form.user}")
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

        # except Exception as e:
        #     logger.error(f">> Form webhook fail, {e}")

    return http.HTTPStatus.ACCEPTED
