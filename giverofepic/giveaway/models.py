from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
import requests
import json

from django.utils import timezone

from giverofepic.settings import USED_HOST
from integrations.models import FormResult
from wallet.default_settings import (
    ERROR, SUCCESS, QUIZ_LINKS_LIFETIME_MINUTES, LOCAL_WALLET_API_URL, API_KEY_HEADER, QUIZ_API_KEY
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
    expires = models.DateTimeField(default=timezone.now() + timedelta(minutes=QUIZ_LINKS_LIFETIME_MINUTES))
    address = models.CharField(max_length=128, help_text="receiver wallet address", blank=True)
    amount = models.DecimalField(max_digits=16, decimal_places=3, help_text="amount of currency to send")
    event = models.CharField(max_length=64, default='giveaway')
    code = models.CharField(max_length=64, default='')

    def get_url(self):  # that mean we have giveaway link
        """https://giverofepic.com/claim/GIVEAWAY_0.01-Vex_hp45tR"""
        if not self.code:
            amount = int(self.amount) if 0 < self.amount > 1 else f"{self.amount:.2f}"
            timestamp = int(self.timestamp.timestamp())
            code_prefix = f"{self.event.upper()[:8]}_{amount}"
            to_encrypt = str((self.address, self.amount, timestamp, self.timestamp.isoformat()))
            code_validator = f"{Encryption(secret_key=self.issuer_api_key).encrypt(to_encrypt)}"
            self.code = f"{code_prefix}-{code_validator[-10:]}"
            self.ready_link = f"{USED_HOST}/claim/{self.code}"
        else:  # that means we have quiz link
            self.ready_link = f"{USED_HOST}/claim/{self.code}"

        self.save()
        return self.ready_link

    @classmethod
    def validate(cls, code: str):
        """
        domain.com/claim/<code>
        https://giverofepic.com/claim/GIVEAWAY_0.01-Vex_hp45tR"""
        link_record = Link.objects.filter(code=code).first()

        if not link_record:
            message = 'Invalid link code (invalid code)'
            logger.error(message)
            return utils.response(ERROR, message)

        if link_record.claimed:
            message = 'Invalid link code (already claimed)'
            logger.warning(message)
            return utils.response(ERROR, message)

        if link_record.expires < timezone.now():
            message = 'Invalid link code (date expired)'
            logger.warning(message)
            return utils.response(ERROR, message)

        if link_record.reusable > 0:
            link_record.reusable -= 1
            link_record.save()
            logger.info(f"Claiming reusable link, {link_record.reusable} times left")

        if link_record.personal and link_record.address:
            logger.info(f"Personal link with address provided")
            cls._process_personal_link(link_record)

        if not link_record.personal:
            logger.info(f"In Blanco link without specified receiver")

            if 'quiz' in link_record.event:
                cls._process_quiz_link(link_record)

            elif 'giveaway' in link_record.event:
                cls._process_in_blanco_link(link_record)
                link_record.claimed = True
                pass

        message = f"link successfully validated"
        logger.info(message)
        return utils.response(SUCCESS, message, link_record)

    @classmethod
    def _process_personal_link(cls, link):
        # TODO: Process personal link
        params = {'address': link.address, 'amount': float(link.amount), 'event': link.event}
        response = cls._wallet_api(query='request_transaction', params=params)

        if not response['error']:
            link.claimed = True
            link.save()

        return response

    @classmethod
    def _process_quiz_link(cls, link):
        # TODO: get user address
        params = {'address': link.address, 'amount': link.amount, 'event': link.event}
        response = cls._wallet_api(query='request_transaction', params=params)

        if not response['error']:
            form = FormResult.objects.get(session_id=link.code)
            form.claimed = True
            form.save()
            link.claimed = True
            link.save()

        return response

    @classmethod
    def _process_in_blanco_link(cls, link):
        # TODO: get user address
        params = {'address': link.address, 'amount': link.amount, 'event': link.event}
        response = cls._wallet_api(query='request_transaction', params=params)

        if not response['error']:
            link.claimed = True
            link.save()

        return response

    @staticmethod
    def _wallet_api(query: str, params: dict):
        url = f"http://{LOCAL_WALLET_API_URL}/{query}"
        headers = {API_KEY_HEADER: QUIZ_API_KEY}
        response = requests.post(url, json=params, headers=headers)

        if response.status_code in [200, 202]:
            return response.json()
        else:
            print(response.text)

    def __str__(self):
        if self.claimed:
            icon = "🟢"
        else:
            icon = "🟡"
        return f"{icon} {self.event.upper()} CODE: {self.amount} {self.currency} -> {get_short(self.address)}"
