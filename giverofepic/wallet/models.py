import decimal
import json
import time
import uuid

from datetime import datetime, timedelta

from django.contrib import admin
from django.db.models import Q
from django.utils import timezone
from ipware import get_client_ip
from django.db import models
import humanfriendly

from wallet import get_short
from wallet.default_settings import *
from wallet.epic_sdk import utils


class WalletState(models.Model):
    # Added by script when initialized, read only/hidden
    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128, default='epic_wallet', unique=True)
    address = models.CharField(max_length=64, default='eZdefault')
    wallet_dir = models.CharField(max_length=128, default='~/.epic/main', editable=False)
    max_amount = models.DecimalField(max_digits=16, decimal_places=3, default=0.01)
    epicbox_port = models.IntegerField(default=EPICBOX_PORT)
    password_path = models.CharField(max_length=128, default=SECRETS_PATH_PREFIX, editable=False)
    epicbox_domain = models.CharField(max_length=64, default=EPICBOX_DOMAIN)

    # Managed by script, read only
    is_locked = models.BooleanField(default=False)
    last_balance = models.JSONField(default=dict, null=True, blank=True)
    last_transaction = models.DateTimeField(blank=True, null=True)

    # Editable for users in admin panel
    description = models.TextField(blank=True, default='Wallet instance used by faucet web-app.')
    default_amount = models.DecimalField(max_digits=16, decimal_places=3, default=0.01)

    def lock(self):
        self.is_locked = True
        self.save()

    def unlock(self):
        self.is_locked = False
        self.save()

    def get_transactions(self):
        return Transaction.objects.filter(wallet_instance=self)

    def update_balance(self, balance: dict):
        self.last_balance = balance
        self.save()

    def __repr__(self):
        return f"WalletState(name='{self.name}', dir='{self.wallet_dir})"

    def __str__(self):
        return f"[{self.name} wallet] {get_short(self.address)}"


@admin.register(WalletState)
class WalletStateAdmin(admin.ModelAdmin):
    readonly_fields = ('name', 'last_balance', 'last_transaction', 'address', 'max_amount',
                       'epicbox_domain', 'epicbox_port', )


class Transaction(models.Model):
    wallet_instance = models.ForeignKey(WalletState, on_delete=models.DO_NOTHING, blank=True, null=True)
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

    def __str__(self):
        return f"Transaction(status={self.status}, " \
               f"{get_short(self.sender_address)} -> {self.amount} -> {get_short(self.receiver_address)}"


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
    # ip_, created = IPAddress.objects.get_or_create(address=ip)
    # address_, created = WalletAddress.objects.get_or_create(address=address)
    ip.last_success_tx = timezone.now()
    ip.save()

    address.last_success_tx = timezone.now()
    address.save()

    return ip, address


def connection_authorized(ip, address):
    if ip.is_now_locked():
        return utils.response(ERROR, ip.locked_msg())

    if address.is_now_locked():
        return utils.response(ERROR, address.locked_msg())

    return utils.response(SUCCESS, 'authorized')


class WalletManager:
    """ Helper class to manage multiple wallet instances"""
    wallets = WalletState.objects
    transactions = Transaction.objects

    def get_wallet(self, state_id: str = None, name: str = None):
        """Get wallet instance from database by name, id or transaction id"""
        if state_id or name:
            filter_ = Q(id=state_id) | Q(name=name)
            return self.wallets.filter(filter_).first()

    def get_wallet_by_tx(self, tx_slate_id: str):
        """Get transaction by slate id and return tuple (wallet, transaction)"""
        filter_ = Q(tx_slate_id=tx_slate_id)
        tx = self.transactions.filter(filter_).first()
        if tx:
            return tx.wallet_instance, tx
        else:
            return None, None

    def get_available_wallet(self, wallet_type: str = 'faucet'):
        """Get available (not locked, ready to work) wallet instance"""
        filter_ = Q(name__startswith=wallet_type)
        try_num = NUM_OF_ATTEMPTS
        available_wallet = None

        while not available_wallet and try_num:
            print(f">> {self.wallets.filter(filter_).count()} '{wallet_type}' wallets")

            for wallet in self.wallets.filter(filter_):
                if not wallet.is_locked:
                    available_wallet = wallet
                    break
            if not available_wallet:
                try_num -= 1
                print(f">> No wallet available, {try_num} attempts left")
                time.sleep(ATTEMPTS_INTERVAL)

        return available_wallet


