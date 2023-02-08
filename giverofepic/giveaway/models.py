from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
import requests
import json

from django.utils import timezone

from wallet.default_settings import (
    TRANSACTION_ARGS,
    GIVEAWAY_LINKS_LIFETIME_MINUTES,
    ERROR, SUCCESS
    )
from giverofepic.tools import Encryption, get_secret_value, get_short
from wallet.epic_sdk import utils
from wallet.epic_sdk.utils import logger


# i4uX1o1O.LtnYTozsbpsxMD5KcbKJCARVOyqLO5gNhHOlNL1G9uxM1XFeJMES5G4Y


class Link(models.Model):
    issuer_api_key = models.CharField(max_length=128)
    short_link = models.CharField(max_length=128, default='')
    timestamp = models.DateTimeField(auto_now_add=True)
    reusable = models.IntegerField(default=0, null=True)
    personal = models.BooleanField(default=True)
    currency = models.CharField(max_length=10, default='EPIC')
    claimed = models.BooleanField(default=False)
    expires = models.DateTimeField(default=timezone.now() + timedelta(minutes=GIVEAWAY_LINKS_LIFETIME_MINUTES))
    address = models.CharField(max_length=128, help_text="receiver wallet address", blank=True)
    amount = models.DecimalField(max_digits=16, decimal_places=3, help_text="amount of currency to send")
    event = models.CharField(max_length=64, default='giveaway')

    def get_short_link(self):
        """
        giverofepic.com/giveaway/TW5EPIC-
        """
        pass

    def __str__(self):
        if self.claimed:
            claimed = "🟡"
        else:
            claimed = "🟢"
        return f"{claimed} {self.event.upper()} CODE: {self.amount} {self.currency} -> {get_short(self.address)}"
