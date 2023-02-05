from datetime import datetime, timedelta

from django.utils import timezone
from ipware import get_client_ip
from django.db import models
import humanfriendly

from wallet.default_settings import SUCCESS, ERROR
from wallet.epic_sdk import utils


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


class IPAddress(Receiver):
    """Used to work with request IP addresses"""
    def __str__(self):
        return f"IPAddress({self.address})"


class Client:
    """Manage client connections activity, update time-locks"""
    def __init__(self, request, addr: str):
        # Get or create Receiver model and update last_activity
        self.receiver, created = Receiver.objects.get_or_create(address=addr)
        self.receiver.last_activity = timezone.now()
        if created: self.receiver.last_status = 'created'
        self.receiver.save()

        # Without connecting IP to the receiver wallet address we have to make
        # a separate column and update the last_activity for given IP
        self.ip, is_routable = get_client_ip(request)
        if self.ip:
            self.ip, created = IPAddress.objects.get_or_create(address=self.ip)
            self.ip.last_activity = timezone.now()
            if created: self.ip.last_status = 'created'
            self.ip.save()

    def update_activity(self, status: str = ''):
        for obj in [self.ip, self.receiver]:
            obj.last_activity = timezone.now()
            obj.last_status = status

            if 'failed' not in obj.last_status:
                obj.last_transaction = timezone.now()
            else:
                obj.last_transaction = None

            obj.save()
            obj.is_now_locked()

    def is_locked(self):
        if self.ip.is_now_locked() or self.receiver.is_now_locked():
            return True
        return False

    def __str__(self):
        return f"Client({self.receiver.get_short_address()})"
