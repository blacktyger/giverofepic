import multiprocessing
import threading
import time

from rq import Queue, Worker
import django_rq

from wallet.default_settings import WALLETS, SECRETS_PATH_PREFIX
from wallet.models import WalletState
from wallet import get_secret_value
from wallet.epic_sdk import Wallet


"""Initialize Redis for managing task"""
redis_conn = django_rq.get_connection('default')


for wallet_name in WALLETS:
    print(f">> Initialize {wallet_name} wallet..")

    try:
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
        queue = Queue(wallet_name, default_timeout=800, connection=redis_conn)

        if len(Worker.all(queue=queue)) < 1:
            worker = Worker([queue], connection=redis_conn, name=wallet_name)
            process = multiprocessing.Process(target=worker.work, kwargs={'with_scheduler': True})
            process.start()

        time.sleep(0.3)
        print(f">> Worker {Worker.all(queue=queue)[0].name} running ({Worker.all(queue=queue)[0].state})")

    except Exception as e:
        print(e)
        print(f"No database created yet, skipping initializing wallet")
        pass
