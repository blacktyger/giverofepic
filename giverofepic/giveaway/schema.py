from pydantic import Field
from ninja import Schema


class LinkSchema(Schema):
    event: str | None = Field(default='giveaway')
    codes: list | None
    amount: float | str | int | None = 0.1
    api_key: str
    qr_code: bool | None = False
    expires: int | None = 60 * 24
    address: str | None
    quantity: int | None = 1
    reusable: int | None = 0
    currency: str | None = 'EPIC'
    personal: bool | None = False
