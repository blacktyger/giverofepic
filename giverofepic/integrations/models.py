from pprint import pprint

from django.db import models


class FormResult(models.Model):
    points = models.IntegerField()
    form_id = models.CharField(max_length=64)
    user_id = models.CharField(max_length=64)
    timestamp = models.DateTimeField(auto_now_add=True)
    completed_in_seconds = models.IntegerField()

    @staticmethod
    def from_body(body: dict):
        form = body['form']
        points = body['answer']['point']['tp']
        completed_in = body['answer']['completeSecond']

        data = {
            'points': points,
            'form_id': form['_id'],
            'user_id': form['userId'],
            'completed_in_seconds': completed_in
            }

        return FormResult.objects.create(**data)

    def __str__(self):
        return f"Form(points: {self.points})"