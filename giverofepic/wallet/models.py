import threading
import pickle

from asgiref.sync import sync_to_async
from datetime import datetime
import decimal
import json
import time
import uuid

from ninja_apikey.security import APIKeyAuth, check_apikey
from django.contrib import admin
from django.db.models import Q
from django.db import models
from rq.job import Job
from rq import Queue
import django_rq

from wallet import get_short, get_secret_value
from wallet.epic_sdk.utils import get_logger
from faucet.models import Client, Receiver, IPAddress
from wallet.epic_sdk import utils, Wallet
from wallet.default_settings import *


logger = get_logger()


class WalletState(models.Model):
    # Added by script when initialized, read only/hidden
    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128, default='faucet_1', unique=True)
    address = models.CharField(max_length=64, default='eZdefault')
    wallet_dir = models.CharField(max_length=128, default='~/.epic/main', editable=False)
    max_amount = models.DecimalField(max_digits=16, decimal_places=3, default=0.01)
    epicbox_port = models.IntegerField(default=EPICBOX_PORT)
    password_path = models.CharField(max_length=128, default=SECRETS_PATH_PREFIX, editable=False)
    epicbox_domain = models.CharField(max_length=64, default=EPICBOX_DOMAIN)

    # Managed by script, read only
    is_locked = models.BooleanField(default=False)
    is_listening = models.BooleanField(default=False)
    last_balance = models.JSONField(default=dict, null=True, blank=True)
    last_spendable = models.DecimalField(max_digits=16, decimal_places=3, null=True, default=0)
    last_transaction = models.ForeignKey('Transaction', on_delete=models.SET_NULL, blank=True, null=True)

    # Editable for users in admin panel
    disabled = models.BooleanField(default=True,
                                   help_text="Disable wallet instance and it's processes, use with caution")
    description = models.TextField(blank=True, default='Wallet instance used by faucet web-app.')
    default_amount = models.DecimalField(max_digits=16, decimal_places=3, default=0.01)

    def lock(self):
        self.is_locked = True
        self.save()

    def unlock(self):
        self.is_locked = False
        self.save()

    def get_pending_transactions(self):
        return Transaction.objects.filter(sender=self, archived=False)

    def get_wallet_history(self, fetch_cancelled=False):
        if not fetch_cancelled:
            filter_ = Q(sender=self) and not Q(status="cancelled")
        else:
            filter_ = Q(sender=self)
        return Transaction.objects.filter(filter_)

    def update_balance(self, balance: dict):
        self.last_balance = balance
        self.last_spendable = int(balance['amount_currently_spendable']) / 10**8
        self.save()

    def __repr__(self):
        return f"WalletState(name='{self.name}', dir='{self.wallet_dir})"

    def __str__(self):
        return f"{str('[DISABLED] ') if self.disabled else ''}" \
               f"[{self.name} wallet] {get_short(self.address)} | {self.last_spendable} EPIC"


@admin.register(WalletState)
class WalletStateAdmin(admin.ModelAdmin):
    readonly_fields = ('name', 'last_spendable', 'last_balance', 'last_transaction', 'address', 'max_amount',
                       'epicbox_domain', 'epicbox_port', )


class Transaction(models.Model):
    sender = models.ForeignKey(WalletState, on_delete=models.SET_NULL, null=True)
    receiver = models.ForeignKey(Receiver, on_delete=models.CASCADE)

    minimum_confirmations = models.IntegerField(default=MINIMUM_CONFIRMATIONS)
    encrypted_slate = models.JSONField(blank=True, null=True)
    initial_slate = models.JSONField(blank=True, null=True)
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

    def remove_client_data(self):
        logger.info(f"Purge client data")
        client_data = IPAddress.objects.filter(receiver=self.receiver).first()
        if client_data:
            client_data.receiver = None
            client_data.save()

    def __str__(self):
        return f"Tx({self.status}, {get_short(self.tx_slate_id, True)} | " \
               f"{self.timestamp.strftime('%H:%M:%S')}, " \
               f"{self.sender.name} -> {self.amount:.2f} -> " \
               f"{self.receiver.get_short_address()})"


class WalletManager:
    """ Helper class to manage multiple wallet instances"""
    wallets = WalletState.objects
    transactions = Transaction.objects

    """Initialize Redis for managing task"""
    redis_conn = django_rq.get_connection('default')

    def __init__(self):
        self.slate_listener = None

        try:
            wallet_instances = WalletState.objects.all().count()
            if wallet_instances < 1:
                logger.warning(">> NO WALLET INSTANCES AVAILABLE, INITIALIZE DEFAULT")
                self._init_default()
            else:
                logger.info(f">> {wallet_instances} WALLET INSTANCES AVAILABLE")
        except Exception as e:
            logger.error(f">> CAN'T INITIALIZE WALLETS, DATABASE ERRORS \n {str(e)}")

    def _init_default(self):
        for wallet_name in WALLETS:
            logger.info(f">> Initialize {wallet_name} wallet..")

            # Get secret values stored and encrypted on the server
            password_path = f"{SECRETS_PATH_PREFIX}/{wallet_name}/password"
            wallet_dir = f"{SECRETS_PATH_PREFIX}/{wallet_name}/dir"

            # Get or create instance from local database
            wallet_instance, _ = WalletState.objects.get_or_create(
                name=wallet_name,
                wallet_dir=get_secret_value(wallet_dir),
                password_path=password_path
                )

            # Initialize Wallet class from PythonSDK
            wallet = Wallet(
                wallet_dir=wallet_instance.wallet_dir,
                password=get_secret_value(wallet_instance.password_path)
                )
            wallet_instance.address = wallet.epicbox.address
            wallet_instance.save()

            # Initialize queue and run redis worker to consume this instance tasks
            queue = Queue(wallet_name, default_timeout=800, connection=self.redis_conn)

            # SPAWNING REDIS WORKER WITHIN SCRIPT, NOT SURE A GOOD IDEA
            # if not Worker.find_by_key(worker_key=f"rq:worker:{wallet_name}_worker", connection=redis_conn):
            #     worker = Worker([queue], connection=redis_conn, name=f"{wallet_name}_worker")
            #     process = multiprocessing.Process(target=worker.work, kwargs={'with_scheduler': True})
            #     process.start()
            #     # logger.info(f">> Worker {worker.name} running ({worker.get_state()})")
            # else:
            #     worker = Worker.find_by_key(worker_key=f"rq:worker:{wallet_name}_worker", connection=redis_conn)
            #     try: worker.work()
            #     except Exception: pass
            #     logger.info(f">> Worker {worker.name} running ({worker.get_state()})")
            # ===========================================================

    def _run_listener(self):
        while self.slate_listener:
            self.get_pending_slates()
            time.sleep(5)

    def run_listener(self):
        logger.info(f">> Starting slate_listener thread..")
        self.slate_listener = threading.Thread(target=self._run_listener)
        self.slate_listener.start()

    def get_pending_slates(self):
        # Get active wallet instances
        filter_ = Q(disabled=False) and Q(is_listening=True)

        for wallet_instance in self.wallets.filter(filter_):

            logger.info(">> Getting pending transactions from local database..")
            pending_transactions = wallet_instance.get_pending_transactions()

            # Ignore if there is no pending transactions in local database (save requests)
            if not pending_transactions.filter(status='initialized').count():
                logger.info(">> No new pending transactions")
                continue

            # """ PREPARE TASK TO ENQUEUE """ #
            job_id = str(uuid.uuid4())
            args = tuple(pickle.dumps(v) for v in [pending_transactions])
            queue = Queue(wallet_instance.name, default_timeout=800, connection=self.redis_conn)
            queue.enqueue('wallet.tasks.finalize_transactions', job_id=job_id, args=args)

    def get_wallet(self, state_id: str = None, name: str = None):
        """Get wallet instance from database by name, id or transaction id"""
        if state_id or name:
            filter_ = Q(diabled=False) and (Q(id=state_id) | Q(name=name))
            return self.wallets.filter(filter_).first()

    def get_wallet_by_tx(self, tx_slate_id: str):
        """Get transaction by slate id and return tuple (wallet, transaction)"""
        tx = self.transactions.filter(tx_slate_id=tx_slate_id).first()
        if tx:
            return tx.sender, tx
        else:
            return None, None

    def get_available_wallet(self, wallet_type: str = 'faucet'):
        """Get available (not locked, ready to work) wallet instance"""
        try_num = NUM_OF_ATTEMPTS
        available_wallet = None

        while not available_wallet and try_num:
            all_wallets = self.wallets.filter(disabled=False, name__startswith=wallet_type)
            logger.info(f">> {all_wallets.count()} '{wallet_type}' wallets")

            for wallet in all_wallets:
                if not wallet.is_locked:
                    available_wallet = wallet
                    break
            if not available_wallet:
                try_num -= 1
                logger.info(f">> No wallet available, {try_num} attempts left")
                time.sleep(ATTEMPTS_INTERVAL)

        logger.info(f">> Available wallet: {available_wallet}")
        return available_wallet

    def enqueue_task(self, wallet_instance: WalletState, target_func, *args, **kwargs):
        """ PREPARE TASK TO ENQUEUE """
        job_id = str(uuid.uuid4())
        args_ = tuple(pickle.dumps(v) for v in args)
        kwargs_ = {k: pickle.dumps(v) for k, v in kwargs.items()}

        queue = Queue(wallet_instance.name, default_timeout=800, connection=self.redis_conn)
        queue.enqueue(target_func, job_id=job_id, args=args_, kwargs=kwargs_)
        return job_id, queue

    def get_task(self, task_id: str):
        task = Job.fetch(task_id, self.redis_conn)
        message = task.meta['message'] if 'message' in task.meta else 'No message'
        return {'status': task.get_status(), 'message': message, 'result': task.result}


class CustomAPIKeyAuth(APIKeyAuth):
    """Custom API async auth"""
    param_name = "X-API-Key"

    @sync_to_async
    def authenticate(self, request, key):
        user = sync_to_async(check_apikey)(key)

        if not user:
            logger.warning("No auth fort the request")
            return False

        request.user = user
        return user