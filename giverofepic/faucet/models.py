import json
from datetime import timedelta
from hashlib import md5
import base64

from asgiref.sync import sync_to_async
from django.utils import timezone
from ipware import get_client_ip
from Crypto.Cipher import AES
from django.db import models
import humanfriendly

from wallet.default_settings import API_KEY_HEADER, ERROR
from wallet.epic_sdk import utils
from wallet.epic_sdk.utils import get_logger

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


class SecureRequest:
    """Manage encrypted requests to secure data traffic with 3rd party apps"""
    BLOCK_SIZE = AES.block_size
    DEFAULT_SECRET_KEY = 'default_secret_key'

    def __init__(self, request):
        secret_key = request.headers.get(API_KEY_HEADER)
        if not secret_key:
            logger.warning(f"Invalid request api-key")
            secret_key = self.DEFAULT_SECRET_KEY
        self.secret_key = secret_key

        self.aes = self._get_aes()
        self.decrypted_data: str = ''
        self.encrypted_data: str = ''

    def _get_aes(self):
        m = md5()
        m.update(self.secret_key.encode('utf-8'))
        key = m.hexdigest()
        m = md5()
        m.update((self.secret_key + key).encode('utf-8'))
        iv = m.hexdigest()

        return AES.new(key.encode("utf8"), AES.MODE_CBC, iv.encode("utf8")[:self.BLOCK_SIZE])

    def _pad(self, byte_array):
        pad_len = self.BLOCK_SIZE - len(byte_array) % self.BLOCK_SIZE
        return byte_array + (bytes([pad_len]) * pad_len)

    @staticmethod
    def _unpad(byte_array):
        return byte_array[:-ord(byte_array[-1:])]

    def encrypt(self, raw_data: dict | str):
        if isinstance(raw_data, dict):
            raw_data = json.dumps(raw_data)
        try:
            data = self._pad(raw_data.encode("UTF-8"))
            self.encrypted_data = base64.urlsafe_b64encode(self.aes.encrypt(data)).decode('utf-8')
            return self.encrypted_data
        except Exception as e:
            logger.warning(f"encryption failed, {e}")

    def decrypt(self, encrypted_data: str):
        try:
            e_data = base64.urlsafe_b64decode(encrypted_data)
            self.decrypted_data = self._unpad(self.aes.decrypt(e_data)).decode('utf-8')
            payload = json.loads(self.decrypted_data)

            if isinstance(payload, dict):
                return payload

        except Exception as e:
            logger.warning(f"decryption failed, {e}")

        return None