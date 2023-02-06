from ninja import Schema


class PayloadSchema(Schema):
    address: str
    amount: float
    wallet_type: str

