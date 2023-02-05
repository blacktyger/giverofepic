from ninja import Schema, ModelSchema
from .models import *


class CancelTransaction(Schema):
    receiving_address: str
    tx_slate_id: str


class PayloadSchema(Schema):
    address: str
    amount: float
    wallet_type: str

