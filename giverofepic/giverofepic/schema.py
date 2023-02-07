from ninja import Schema
from pydantic import Field


class LinkSchema(Schema):
    issuer_api_key: str | None = Field(default='')
    address: str
    amount: float | str | int
    event: str | None = Field(default='giveaway')