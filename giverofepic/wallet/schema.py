from ninja import Schema


class CancelTransaction(Schema):
    receiving_address: str
    tx_slate_id: str


class TxRequestSchema(Schema):
    receiver_address: str
    code: str
    data: dict | None = {}

