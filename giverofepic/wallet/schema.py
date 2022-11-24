from ninja import Schema

class SlateIn(Schema):
    pass

class TransactionIn(Schema):
    address: str
    amount: float
