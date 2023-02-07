from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
import requests
import json

from django.utils import timezone

from wallet.default_settings import (
    GIVEAWAY_LINKS_PATH,
    GIVEAWAY_LINKS_DOMAIN,
    GIVEAWAY_LINKS_API_KEY_PATH,
    GIVEAWAY_LINK_LIFETIME_MINUTES, TRANSACTION_ARGS
    )
from giverofepic.tools import Encryption, get_secret_value, get_short
from wallet.epic_sdk.utils import logger


# hwraX9qO.aXzSiWEKZXiy6E7LDKAiJwL5VIyfw1qrtnDnQYII1ad2EXMjHhQ6z1bq


class Code(models.Model):
    already_claimed = models.BooleanField(default=False)
    issuer_api_key = models.CharField(max_length=128)
    link_lifetime = models.DateTimeField(default=timezone.now() + timedelta(minutes=GIVEAWAY_LINK_LIFETIME_MINUTES))
    link_domain = models.CharField(max_length=64, default=f"{GIVEAWAY_LINKS_DOMAIN}")
    link_prefix = models.CharField(max_length=64, default=f"{GIVEAWAY_LINKS_PATH}")
    timestamp = models.DateTimeField(auto_now_add=True)
    currency = models.CharField(max_length=10, default='EPIC')
    address = models.CharField(max_length=128, help_text="receiver wallet address")
    amount = models.DecimalField(max_digits=16, decimal_places=3, help_text="amount of currency to send")
    event = models.CharField(max_length=64, default='Giveaway')

    def encrypt(self):
        data = {
            'timestamp': str(self.timestamp.utcnow()),
            'currency': self.currency,
            'address': self.address,
            'amount': self.amount,
            'event': self.event
            }

        return Encryption(self.issuer_api_key).encrypt(data)

    @staticmethod
    def from_encrypted(encrypted_data: str, secret_key: str):
        data = Encryption(secret_key).decrypt(encrypted_data)
        data['issuer_api_key'] = secret_key
        logger.info(data)

        if all(args in TRANSACTION_ARGS for args in data):
            return Code(**data)

    def get_short_link(self):
        link_prefix = f"https://{self.link_prefix}/code="
        destination = f"{link_prefix}{self.encrypt()}"
        rebrandly_apikey = get_secret_value(GIVEAWAY_LINKS_API_KEY_PATH)

        requestHeaders = {
            "Content-type": "application/json",
            "apikey": rebrandly_apikey,
            "workspace": "e9b41228264a4f5e94089e83c73c2b76"
            }
        print(destination)
        r = requests.get(f"https://api.rebrandly.com/v1/links/new?"
                         f"destination={destination}&"
                         f'domain[id]=d983e29e62e94729b2456c278976e33f',
                         headers=requestHeaders)
        print(r.text)
        if r.status_code == requests.codes.ok:
            return r.json()

    def __str__(self):
        if self.already_claimed:
            claimed = "🟡"
        else:
            claimed = "🟢"

        return f"{claimed} {self.event.upper()} CODE: {self.amount} {self.currency} -> {get_short(self.address)}"
