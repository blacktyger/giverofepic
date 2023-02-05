from datetime import datetime, timedelta

from django.utils import timezone
from ipware import get_client_ip
from django.db import models
import humanfriendly

from wallet.default_settings import SUCCESS, ERROR
from wallet.epic_sdk import utils


class Address(models.Model):
    address = models.CharField(max_length=256)
    is_banned = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    last_activity = models.DateTimeField(auto_now_add=True)
    last_success_tx = models.DateTimeField(null=True, blank=True)
    TIME_LOCK_SECONDS = models.IntegerField(default=60)

    def get_short(self):
        try:
            return f"{self.address[0:4]}...{self.address[-4:]}"
        except Exception:
            return self.address

    def locked_for(self):
        if not self.last_success_tx or not self.is_locked:
            return 0
        else:
            return self.last_success_tx + timedelta(seconds=self.TIME_LOCK_SECONDS) - timezone.now()

    def locked_msg(self):
        return f'You have reached your limit, try again in ' \
               f'<b>{humanfriendly.format_timespan(self.locked_for().seconds)}</b>.'

    def is_now_locked(self):
        if not self.last_success_tx:
            self.is_locked = False
        else:
            self.is_locked = (timezone.now() - self.last_success_tx) < timedelta(seconds=self.TIME_LOCK_SECONDS)

        self.save()
        return self.is_locked


class WalletAddress(Address):
    """Used to work with epic-wallet addresses"""
    def __str__(self):
        return f"WalletAddress(address='{self.get_short()}', locked: {self.is_locked})"


class IPAddress(Address):
    """Used to work with request IP addresses"""
    def __str__(self):
        return f"IPAddress(address='{self.address}', locked: {self.is_locked})"


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
