from datetime import timedelta
from cryptography.fernet import Fernet

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


# hwraX9qO.aXzSiWEKZXiy6E7LDKAiJwL5VIyfw1qrtnDnQYII1ad2EXMjHhQ6z1bq


class Link(models.Model):
    already_claimed = models.BooleanField(default=False)
    issuer_api_key = models.CharField(max_length=128)
    link_lifetime = models.DateTimeField(default=timezone.now() + timedelta(minutes=GIVEAWAY_LINKS_LIFETIME_MINUTES))
    short_link = models.CharField(max_length=128, default='')
    timestamp = models.DateTimeField(auto_now_add=True)
    currency = models.CharField(max_length=10, default='EPIC')
    amount = models.DecimalField(max_digits=16, decimal_places=3, help_text="amount of currency to send")
    event = models.CharField(max_length=64, default='Giveaway')

    """
    giverofepic.com/giveaway/TW5EPIC-
    """

    def get_short_link(self):
        pass

    def __str__(self):
        if self.already_claimed:
            claimed = "🟡"
        else:
            claimed = "🟢"
        return f"{claimed} {self.event.upper()} CODE: {self.amount} {self.currency} -> {get_short(self.address)}"


class PersonalLink(Link):
    address = models.CharField(max_length=128, help_text="receiver wallet address")


class InBlancoLink(Link):
    reusable = models.IntegerField(default=0, null=True)