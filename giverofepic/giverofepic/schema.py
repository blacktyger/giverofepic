from datetime import datetime

from ninja import Schema
from pydantic import Field


class LinkSchema(Schema):
    issuer_api_key: str | None = Field(default='')
    personal: bool
    reusable: int
    currency: str
    address: str | None
    expires: datetime
    amount: float | str | int
    event: str | None = Field(default='giveaway')