from ninja import Schema, ModelSchema
from .models import *


class CancelTransaction(Schema):
    receiving_address: str
    tx_slate_id: str


class TransactionSchema(ModelSchema):
    class Config:
        model = Transaction
        model_fields = ["amount", "receiver_address"]

