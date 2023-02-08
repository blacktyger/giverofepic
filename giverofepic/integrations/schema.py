from ninja import Schema


class PayloadSchema(Schema):
    form: dict
    answer: dict