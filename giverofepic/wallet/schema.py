from ninja import Schema


class PayloadSchema(Schema):
    address: str
    amount: float | str | int
    event: str


class EncryptedPayloadSchema(Schema):
    data: str


class CancelPayloadSchema(Schema):
    tx_slate_id: str