from ninja import Schema


class FormResultSchema(Schema):
    form: dict
    answer: dict