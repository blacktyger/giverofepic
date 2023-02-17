from datetime import timedelta
from pprint import pprint

import humanfriendly
from django.db import models
from django.utils import timezone

from wallet.default_settings import QUIZ_USER_TIME_LOCK_MINUTES, QUIZ_MIN_POINT_FOR_REWARD
from wallet.epic_sdk.utils import logger


class FormUser(models.Model):
    id = models.CharField(max_length=32, unique=True, primary_key=True)
    username = models.CharField(max_length=64, default='')
    full_name = models.CharField(max_length=64, default='')

    @staticmethod
    def from_body(body: dict):
        if not body: return None

        id_ = body['answer']['userId']
        user, created = FormUser.objects.get_or_create(id=id_)

        if created:
            for k, v in body['answer']['userInfo'].items():
                setattr(user, k, v)

            user.save()
            logger.info(f'Added new {user}')

        return user

    def get_forms(self):
        return self.forms.order_by('timestamp')

    def last_rewarded_form(self):
        return self.get_forms().filter(
            is_valid=True,
            points__gt=QUIZ_MIN_POINT_FOR_REWARD,
            timestamp__gte=timezone.now() - timedelta(minutes=QUIZ_USER_TIME_LOCK_MINUTES)
            )

    def is_locked(self):
        if self.last_rewarded_form():
            return True
        return False

    def locked_for(self):
        form = self.last_rewarded_form()

        if form:
            locked_for_ = form.get_expire_date() - timezone.now()
            message = f'You have reached your limit, try again in ' \
                      f'<b>{humanfriendly.format_timespan(locked_for_.seconds)}</b>.'

            return locked_for_, message

        return None, None

    def __str__(self):
        if not self.is_locked():
            icon = "🟢"
        else:
            icon = "🟡"
        return f"{icon} FormUser({self.username if self.username else self.id})"


class FormResult(models.Model):
    user = models.ForeignKey(FormUser, on_delete=models.CASCADE, blank=True, null=True, related_name='forms')
    points = models.IntegerField()
    reward = models.IntegerField(default=0, null=True)
    form_id = models.CharField(max_length=64)
    is_valid = models.BooleanField(default=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    session_id = models.CharField(max_length=64)
    completed_in_seconds = models.IntegerField()

    @staticmethod
    def get_reward(points):
        if QUIZ_MIN_POINT_FOR_REWARD <= points < 8:
            reward = 1
        elif 8 <= points < 10:
            reward = 5
        elif 10 <= points:
            reward = 10
        else:
            reward = 0

        return reward

    def get_expire_date(self):
        return self.timestamp + timedelta(minutes=QUIZ_USER_TIME_LOCK_MINUTES)

    @staticmethod
    def from_body(body: dict):
        if not body: return None

        form = body['form']
        points = int(body['answer']['point']['tp'])
        reward = FormResult.get_reward(points)
        completed_in = body['answer']['completeSecond']

        data = {
            'user': body['user'],
            'points': points,
            'reward': reward,
            'form_id': form['_id'],
            'session_id': body['answer']['publicId'],
            'completed_in_seconds': completed_in
            }

        return FormResult.objects.create(**data)

    def __str__(self):
        return f"FormResult(points: {self.points})"
