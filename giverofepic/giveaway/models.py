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
    ready_link = models.CharField(max_length=128, default='')
    timestamp = models.DateTimeField(auto_now_add=True)
    reusable = models.IntegerField(default=0, null=True)
    personal = models.BooleanField(default=True)
    currency = models.CharField(max_length=10, default='EPIC')
    claimed = models.BooleanField(default=False)
    expires = models.DateTimeField(default=timezone.now() + timedelta(minutes=GIVEAWAY_LINKS_LIFETIME_MINUTES))
    address = models.CharField(max_length=128, help_text="receiver wallet address", blank=True)
    amount = models.DecimalField(max_digits=16, decimal_places=3, help_text="amount of currency to send")
    event = models.CharField(max_length=64, default='giveaway')
    code = models.CharField(max_length=64, default='')

    def get_url(self):
        """https://giverofepic.com/claim/GIVEAWAY_0.01-Vex_hp45tR"""
        amount = int(self.amount) if self.amount > 1 else f"{self.amount:.2f}"
        timestamp = int(self.timestamp.timestamp())
        code_prefix = f"{self.event.upper()[:8]}_{amount}"
        to_encrypt = str((self.address, self.amount, timestamp))  # self.timestamp.isoformat()))
        print(to_encrypt)

        code_validator = f"{Encryption(secret_key=self.issuer_api_key).encrypt(to_encrypt)}"
        print(code_validator)

        self.code = f"{code_prefix}-{code_validator[-10:]}"
        self.ready_link = f"https://giverofepic.com/claim/{self.code}"
        self.save()

        return self.ready_link

    @staticmethod
    def validate(short_link: str):
        """https://giverofepic.com/claim/GIVEAWAY_0.01-Vex_hp45tR"""
        link_record = Link.objects.filter(short_link=short_link).first()

        if not link_record:
            logger.error('Invalid link code (invalid code)')
            return None

        if link_record.claimed:
            logger.warning('Invalid link code (already claimed)')
            return None

        if link_record.expires < timezone.now():
            logger.warning('Invalid link code (date expired)')
            return None

        if link_record.reusable > 0:
            link_record.reusable -= 1
            link_record.save()
            logger.info(f"Claiming reusable link, {link_record.reusable} times left")

        if link_record.personal and link_record.address:
            logger.info(f"Personal link with address provided")
            # TODO: Accept the link and send transaction

        if not link_record.personal and not link_record.address:
            logger.info(f"In Blanco link without specified receiver")
            # TODO: Accept the link and redirect to address form

        logger.info(f"Personal link successfully processed and reward claimed")

    def __str__(self):
        if self.claimed:
            icon = "🟢"
        else:
            icon = "🟡"
        return f"{icon} {self.event.upper()} CODE: {self.amount} {self.currency} -> {get_short(self.address)}"
