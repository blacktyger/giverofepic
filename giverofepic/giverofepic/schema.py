from datetime import datetime, timedelta

from django.utils import timezone
from pydantic import Field
from ninja import Schema

from wallet.default_settings import GIVEAWAY_LINKS_LIFETIME_MINUTES


class LinkSchema(Schema):
    issuer_api_key: str | None = Field(default='')
    personal: bool | None = True
    reusable: int | None = 0
    currency: str | None = 'EPIC'
    address: str | None = 'receiver_address'
    expires: datetime | None = timezone.now() + timedelta(minutes=GIVEAWAY_LINKS_LIFETIME_MINUTES)
    amount: float | str | int | None = 0.01
    event: str | None = Field(default='giveaway')