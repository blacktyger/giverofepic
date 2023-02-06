from ninja import Schema


class PayloadSchema(Schema):
    amount: float | str | int
    address: str
    wallet_type: str


class EncryptedPayloadSchema(Schema):
    data: str


class CancelPayloadSchema(Schema):
    tx_slate_id: str