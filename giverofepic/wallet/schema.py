from ninja import Schema


class TransactionPayloadSchema(Schema):
    address: str
    amount: float | str | int
    event: str


class CancelPayloadSchema(Schema):
    tx_slate_id: str