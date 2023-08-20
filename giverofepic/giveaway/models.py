from datetime import timedelta
import uuid

import django_rq
from django.db import models, IntegrityError
from django.contrib.auth.models import User
from django.utils import timezone
import qrcode

from giverofepic.settings import (USED_HOST, CLAIM_LINK_API_KEYS as API_KEYS)
from wallet.default_settings import (ERROR, SUCCESS)

from wallet.epic_sdk.utils import logger
from wallet.models import Transaction
from wallet.epic_sdk import utils

"""Initialize Queue for managing task"""
redis_conn = django_rq.get_connection('default')


class Link(models.Model):
    """Claim links used to distribute giveaways"""

    transaction = models.OneToOneField(
        Transaction, on_delete=models.SET_NULL, null=True, blank=True,
        help_text='Transaction associated with this link')
    ready_url = models.CharField(
        default='', blank=True, editable=False, max_length=128, help_text="URL link for the end-user")
    event = models.CharField(
        default='giveaway', max_length=64, help_text="Name of the event")
    amount = models.DecimalField(
        default=0.1, max_digits=16, decimal_places=3, help_text="Reward value")
    address = models.CharField(
        max_length=128, blank=True, help_text="Receiver wallet address (only for 'Personal' links")
    quantity = models.IntegerField(
        default=1, help_text="Number of links to create (same details are used)")
    claim_date = models.DateTimeField(
        null=True, blank=True, help_text="When link was claimed")
    timestamp = models.DateTimeField(
        auto_now_add=True, help_text="When link was created")
    reusable = models.IntegerField(
        default=0, null=True, help_text="How many times link can be used")
    personal = models.BooleanField(
        default=False, help_text="Link valid only for that address")
    currency = models.CharField(
        default='EPIC', max_length=10, help_text="Reward currency")
    claimed = models.BooleanField(
        default=False, help_text="(DO NOT EDIT) Link was claimed")
    expires = models.DateTimeField(
        default=timezone.now() + timedelta(minutes=60), help_text="Link expiry date")
    code = models.CharField(
        max_length=64, default=f"temp_{uuid.uuid4()}", unique=True, help_text="Link unique validation code")
    qr_code = models.BooleanField(
        default=False, help_text="Create a QR code for the URL")
    api_key = models.CharField(
        default=API_KEYS[0], editable=False, max_length=128, help_text="API KEY to authorize link creation")

    __was_claimed = None

    class Meta:
        ordering = ["-claim_date", "-transaction"]

    def __init__(self, *args, **kwargs):
        """
        Register Link object creating its associated URL link to claim
        EXAMPLE: https://giverofepic.com/claim/<CODE>
        """
        super().__init__(*args, **kwargs)
        self.__was_claimed = self.claimed

        # Create more similar links (different codes & ready_urls)
        if self.quantity > 1:
            link_params = self.__dict__.copy()
            link_params.pop('transaction_id')
            link_params.pop('__was_claimed', None)
            link_params.pop('timestamp')
            link_params.pop('_state')
            link_params.pop('code')
            link_params.pop('id')

            self.create_batch(**link_params)
            self.quantity = 1
            self.save()

    def save(self, *args, **kwargs):
        # If 'code' is not provided generate it from the provided data
        if not self.code or self.code.startswith('temp_'):
            amount = int(self.amount) if 0 < self.amount > 1 else f"{self.amount:.2f}"
            code_prefix = f"{self.event.upper()[:8]}_{amount}"
            self.code = f"{code_prefix}_{str(uuid.uuid4()).split('-')[-1]}"
            self.ready_url = f"{USED_HOST}/claim/{self.code}"

        # otherwise use provided code
        else:
            self.ready_url = f"{USED_HOST}/claim/{self.code}"

        # Update claim_date date if self.claimed changes
        if self.__was_claimed != self.claimed:
            if self.claimed:
                self.claim_date = timezone.now()
            else:
                self.claim_date = None

        if self.qr_code:
            img = qrcode.make(self.ready_url)
            img.save(f'static/img/qr_codes/{self.code}.png')

        try:
            super().save(*args, **kwargs)
            self.__was_claimed = self.claimed

        except IntegrityError as e:
            if 'unique constraint' in e.args:
                logger.error(f'Unlucky constraint for {self.code}')

    @staticmethod
    def create_batch(**kwargs):  # quantity: int, codes: list = list,
        logger.info(f">> start working on task create_links_batch")
        quantity = kwargs['quantity']
        kwargs.pop('_Link__was_claimed', None)
        kwargs['quantity'] = 1

        links = [Link.objects.create(**kwargs) for _ in range(quantity)]
        return utils.response(SUCCESS, f"{len(links)} links created", links)

    def update_params(self, **kwargs):
        """Update link parameters in the database"""
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.save()

    @classmethod
    def validate(cls, code: str):
        """
        domain.com/claim/<code>
        """

        link_record = Link.objects.filter(code=code).first()

        if not link_record:
            message = 'Invalid code'
            return utils.response(ERROR, message)

        message = f"{link_record} successfully validated"
        logger.info(message)
        return utils.response(SUCCESS, message, link_record)

    def tx_params(self):
        return {
            'receiver_address': self.address,
            'amount': float(self.amount),
            'event': self.event
            }

    # def request_transaction(self):
    #     params = {
    #         'address': self.address,
    #         'amount': float(self.amount),
    #         'event': self.event,
    #         'code': self.code
    #         }
    #     response = self._wallet_api(query='request_transaction', params=params)
    #
    #     if not response['error']:
    #         # If link is reusable update its counter
    #         if self.reusable > 0:
    #             self.reusable -= 1
    #             self.save()
    #             logger.info(f"Claiming reusable link, {self.reusable} times left")
    #
    #         self.claimed = True
    #         self.save()
    #
    #     return response

    # @classmethod
    # def _process_quiz_link(cls, link):
    #     # TODO: get user address
    #     params = {'address': link.address, 'amount': float(link.amount), 'event': link.event}
    #     response = cls._wallet_api(query='request_transaction', params=params)
    #
    #     if not response['error']:
    #         form = FormResult.objects.get(session_id=link.code)
    #         form.claimed = True
    #         link.claimed = True
    #         form.save(), link.save()
    #
    #     return response

    # @classmethod
    # def _process_in_blanco_link(cls, link):
    #     # TODO: get user address
    #     params = {'address': link.address, 'amount': float(link.amount), 'event': link.event}
    #     response = cls._wallet_api(query='request_transaction', params=params)
    #
    #     if not response['error']:
    #         link.claimed = True
    #         link.save()
    #
    #     return response
    #
    # @staticmethod
    # def _wallet_api(query: str, params: dict):
    #     url = f"http://{LOCAL_WALLET_API_URL}/{query}"
    #     headers = {API_KEY_HEADER: GIVEAWAY_API_KEY}
    #     response = requests.post(url, json=params, headers=headers)
    #
    #     if response.status_code in [200, 202]:
    #         if response.json()['error']:
    #             logger.error(response.json()['message'])
    #         return response.json()
    #     else:
    #         print(response.text)

    def __str__(self):
        tx_id = ''
        icon = "🔘"

        if self.transaction:
            tx_id = f"| {str(self.transaction.tx_slate_id).split('-')[-1]}"

            if self.transaction.status == 'finalized':
                icon = "✅"
            elif self.transaction.status == 'pending':
                icon = "☑️"
            elif self.transaction.status == 'failed':
                icon = "🛑"
        else:
            if self.claimed:
                icon = "🟡"

        return f"{icon} {self.event.upper()}: {self.amount} {self.currency} | {self.code} {tx_id}"
