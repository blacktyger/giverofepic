import datetime
import decimal
import json

from django.db import models


class Wallet(models.Model):
    id = models.UUIDField(primary_key=True, unique=True)
    name = models.CharField(max_length=128, default='default')
    locked = models.BooleanField(default=False)

    def __str__(self):
        return f"Wallet(name={self.name})"


class EpicBoxAddress(models.Model):
    address = models.CharField(max_length=256)

    def __str__(self):
        return f"EpicBoxAddress(address={self.address})"

class UserIP(models.Model):
    address = models.CharField(max_length=24)

    def __str__(self):
        return f"UserIP(address={self.address})"

class Transaction(models.Model):
    receiver_address = models.CharField(max_length=256)
    sender_address = models.CharField(max_length=256)
    wallet_db_id = models.IntegerField()
    tx_slate_id = models.UUIDField()
    timestamp = models.DateTimeField()
    tx_type = models.CharField(max_length=24)
    amount = models.DecimalField(max_digits=24, decimal_places=8)
    status = models.CharField(max_length=256)
    slates = models.JSONField(blank=True, null=True)

    @staticmethod
    def parse_init_slate(raw_slate: str):
        slate_ = json.loads(raw_slate)
        db_tx, network_slate = slate_
        args = json.loads(db_tx)[0]

        response = {
            "wallet_db_id": args['id'],
            "tx_slate_id": args['tx_slate_id'],
            "timestamp": datetime.datetime.fromisoformat(args['creation_ts']),
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
            "timestamp": datetime.datetime.fromisoformat(args['creation_ts']),
            "tx_type": args['tx_type'],
            "amount": decimal.Decimal(str(int(args['amount_credited']) / 10 ** 8))
            }

        print(response)

    def __str__(self):
        return f"Transaction(tx_status={self.status}, tx_slate_id={self.tx_slate_id})"


