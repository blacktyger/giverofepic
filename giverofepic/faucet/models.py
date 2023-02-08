from datetime import timedelta

from asgiref.sync import sync_to_async
from django.utils import timezone
from ipware import get_client_ip
from django.db import models
import humanfriendly

from wallet.default_settings import API_KEY_HEADER, DEFAULT_SECRET_KEY
from wallet.epic_sdk.utils import get_logger
from giverofepic.tools import Encryption

logger = get_logger()


class Receiver(models.Model):
    address = models.CharField(max_length=256)
    is_banned = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    last_status = models.TextField(blank=True)
    last_activity = models.DateTimeField(auto_now_add=True)
    last_transaction = models.DateTimeField(null=True, blank=True)
    TIME_LOCK_SECONDS = models.IntegerField(default=60)

    def get_short_address(self):
        try:
            return f"{self.address[0:4]}...{self.address[-4:]}"
        except Exception:
            return self.address

    def locked_for(self):
        if not self.last_transaction or not self.is_locked:
            return 0
        else:
            return self.last_transaction + timedelta(seconds=self.TIME_LOCK_SECONDS) - timezone.now()

    @sync_to_async
    def locked_msg(self):
        return f'You have reached your limit, try again in ' \
               f'<b>{humanfriendly.format_timespan(self.locked_for().seconds)}</b>.'

    def is_now_locked(self):
        if not self.last_transaction:
            self.is_locked = False
        else:
            self.is_locked = (timezone.now() - self.last_transaction) < timedelta(seconds=self.TIME_LOCK_SECONDS)
        self.save()
        return self.is_locked

    def __str__(self):
        return f"Receiver({self.get_short_address()})"


class IPAddress(models.Model):
    """Used to work with request IP addresses"""
    receiver = models.ForeignKey(Receiver, on_delete=models.CASCADE, null=True, default=None, related_name="ip")
    address = models.CharField(max_length=256, null=True, blank=True)

    def __str__(self):
        return f"IPAddress({self.address})"


class Client:
    """Manage client connections activity, update time-locks"""
    def __init__(self, ip_address: str, wallet_address: str):
        # Get or create Receiver model and update last_activity
        self.receiver, created = Receiver.objects.get_or_create(address=wallet_address)
        if created: self.receiver.last_status = 'created'
        self.receiver.last_activity = timezone.now()
        self.receiver.save()

        # We will connect IP to the receiver wallet address during transaction time
        # and purge that data when process is finished (either success or fail/cancel)
        self.ip, created = IPAddress.objects.get_or_create(address=ip_address, receiver=self.receiver)

    @staticmethod
    @sync_to_async
    def from_request(request, wallet_address):
        try:
            ip_address, is_routable = get_client_ip(request)
        except Exception as e:
            logger.warning(f">> Can't extract ip_address from request object\n {e}")
            ip_address = '54.54.54.54'  # Add dummy IP ADDRESS
        return Client(ip_address, wallet_address)

    @staticmethod
    def from_receiver(receiver: Receiver):
        try:
            ip_address = receiver.ip.first().address
        except Exception as e:
            logger.warning(f"{receiver} have no ip_address assigned\n {e}")
            ip_address = '54.54.54.54'  # Add dummy IP ADDRESS
        wallet_address = receiver.address
        return Client(ip_address, wallet_address)

    @sync_to_async
    def is_allowed(self):
        return not self.receiver.is_now_locked()

    def update_activity(self, status: str = ''):
        self.receiver.last_activity = timezone.now()
        self.receiver.last_status = status

        if any(reason in ['failed', 'cancelled'] for reason in self.receiver.last_status):
            self.receiver.last_transaction = None
        else:
            self.receiver.last_transaction = timezone.now()

        self.receiver.save()
        self.receiver.is_now_locked()

        return f"{self} activity updated | last_tx: {self.receiver.last_transaction}"

    def __str__(self):
        return f"Client({self.receiver.get_short_address()})"


class SecureRequest(Encryption):
    """Manage encrypted requests to secure data traffic with 3rd party apps"""

    def __init__(self, request):
        secret_key = request.headers.get(API_KEY_HEADER)
        if not secret_key:
            logger.warning(f"Invalid request api-key")
            secret_key = DEFAULT_SECRET_KEY
        self.secret_key = secret_key

        super().__init__(secret_key)