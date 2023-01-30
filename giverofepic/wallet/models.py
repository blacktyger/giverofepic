import platform
import decimal
import json
import time
import uuid

from datetime import datetime, timedelta
from django.utils import timezone
from ipware import get_client_ip
from django.db import models
import humanfriendly

from giverofepic.secrets import WALLET_DIR
from wallet.epic_sdk import utils
from wallet.default_settings import *


class WalletState(models.Model):
    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4)
    name = models.CharField(max_length=128, default='epic_wallet')
    is_locked = models.BooleanField(default=False)
    wallet_dir = models.CharField(max_length=128, default=WALLET_DIR)

    def lock(self):
        self.is_locked = True
        self.save()

    def unlock(self):
        self.is_locked = False
        self.save()

    def error_msg(self):
        return "Wallet can not process your request now, try again later."

    def __str__(self):
        return f"WalletState(name='{self.name}', dir='{self.wallet_dir})"


class Address(models.Model):
    """Base class for authorization incoming transaction requests."""
    address = models.CharField(max_length=256)
    is_banned = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    last_activity = models.DateTimeField(auto_now_add=True)
    last_success_tx = models.DateTimeField(null=True, blank=True)

    def locked_for(self):
        if not self.last_success_tx or not self.is_locked:
            return 0
        else:
            return self.last_success_tx + timedelta(minutes=1) - timezone.now()

    def locked_msg(self):
        return f'You have reached your limit, try again in ' \
               f'<b>{humanfriendly.format_timespan(self.locked_for().seconds)}</b>.'

    def is_now_locked(self):
        if not self.last_success_tx:
            self.is_locked = False
        else:
            self.is_locked = (timezone.now() - self.last_success_tx) < timedelta(minutes=1)

        self.save()
        return self.is_locked


class WalletAddress(Address):
    def get_short(self):
        try:
            return f"{self.address[0:4]}...{self.address[-4:]}"
        except Exception:
            return self.address

    def __str__(self):
        return f"WalletAddress(is_locked='{self.is_locked}', address='{self.get_short()}')"


class IPAddress(Address):
    def __str__(self):
        return f"IPAddress(is_locked='{self.is_locked}', address='{self.address}')"


class Transaction(models.Model):
    receiver_address = models.CharField(max_length=254)
    encrypted_slate = models.JSONField(blank=True, null=True)
    sender_address = models.CharField(max_length=254)
    wallet_db_id = models.IntegerField()
    tx_slate_id = models.UUIDField()
    timestamp = models.DateTimeField()
    archived = models.BooleanField(default=False)
    tx_type = models.CharField(max_length=24)
    amount = models.DecimalField(max_digits=24, decimal_places=8)
    status = models.CharField(max_length=256)

    @staticmethod
    def parse_init_slate(raw_slate: str):
        slate_ = json.loads(raw_slate)
        db_tx, network_slate = slate_
        args = json.loads(db_tx)[0]

        response = {
            "wallet_db_id": args['id'],
            "tx_slate_id": args['tx_slate_id'],
            "timestamp": datetime.fromisoformat(args['creation_ts']),
            "tx_type": args['tx_type'],
            "amount": decimal.Decimal(str(int(args['amount_credited']) / 10 ** 8))
            }

        return response

    @staticmethod
    def parse_raw_slates(raw_slate: list):
        if isinstance(raw_slate, str):
            json.loads(raw_slate)

        slate_string, address = raw_slate
        db_tx, network_slate = json.loads(slate_string)
        args = json.loads(db_tx)[0]

        print(args)

        response = {
            "receiver_address": address,
            "wallet_db_id": args['id'],
            "tx_slate_id": args['tx_slate_id'],
            "timestamp": datetime.fromisoformat(args['creation_ts']),
            "tx_type": args['tx_type'],
            "amount": decimal.Decimal(str(int(args['amount_credited']) / 10 ** 8))
            }

        return response

    @staticmethod
    def validate_tx_args(amount: float | int | str, receiver_address: str):
        try:
            if 0.00000001 > float(amount) >= MAX_AMOUNT:
                return utils.response(ERROR, f'Invalid amount (0 < {amount} < {MAX_AMOUNT})')
            elif len(receiver_address.strip()) != 52:
                return utils.response(ERROR, 'Invalid receiver_address')

        except Exception as e:
            return utils.response(ERROR, f'Invalid tx_args, {e}')

        return utils.response(SUCCESS, 'tx_args valid')

    @staticmethod
    def get_short(address):
        try:
            return f"{address[0:4]}...{address[-4:]}"
        except Exception:
            return address

    def __str__(self):
        return f"Transaction(status={self.status}, " \
               f"{self.get_short(self.sender_address)} -> {self.amount} -> {self.get_short(self.receiver_address)}"
               # f"tx_slate_id={self.tx_slate_id})"


def connection_details(request, addr, update: bool = False):
    address, created = WalletAddress.objects.get_or_create(address=addr)
    address.last_activity = timezone.now()

    ip, is_routable = get_client_ip(request)
    if ip:
        ip, created = IPAddress.objects.get_or_create(address=ip)
        ip.last_activity = timezone.now()

    if update: update_connection_details(ip, address)

    return ip, address


def update_connection_details(ip, address):
    ip_, created = IPAddress.objects.get_or_create(address=ip)
    address_, created = WalletAddress.objects.get_or_create(address=address)

    ip_.last_success_tx = timezone.now()
    ip_.save()

    address_.last_success_tx = timezone.now()
    address_.save()

    return ip, address

def connection_authorized(ip, address):
    if ip.is_now_locked():
        return utils.response(ERROR, ip.locked_msg())

    if address.is_now_locked():
        return utils.response(ERROR, address.locked_msg())

    return utils.response(SUCCESS, 'authorized')


def get_wallet_status(wallet):
    """
    :param wallet:
    :return:
    """
    re_try = NUM_OF_ATTEMPTS

    # Refresh wallet state from DB
    WalletState.objects.get(id=wallet.state.id)

    # TRY NUM_OF_ATTEMPTS WITH ATTEMPTS_INTERVAL TILL FAIL
    while WalletState.objects.get(id=wallet.state.id).is_locked and re_try:
        print(f"locked, {re_try} re-try attempts left ")
        re_try -= 1
        time.sleep(ATTEMPTS_INTERVAL)

    if WalletState.objects.get(id=wallet.state.id).is_locked:
        return utils.response(ERROR, wallet.state.error_msg())

    wallet.state = WalletState.objects.get(id=wallet.state.id)
    return utils.response(SUCCESS, 'wallet ready')
