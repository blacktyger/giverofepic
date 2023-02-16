from ninja import Schema


class FormResultSchema(Schema):
    form: dict | None
    answer: dict | None