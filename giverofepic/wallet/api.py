import time
import uuid

import django_rq
from ninja import NinjaAPI
from rq import Queue
from rq.job import Job

from .epic_sdk.utils import get_logger
from .default_settings import *
from .epic_sdk import utils
from . import tasks

from .models import Transaction, connection_details, connection_authorized, WalletState
from .schema import PayloadSchema

api = NinjaAPI()
logger = get_logger()


# TODO: Initialize wallets via `setup_wallet.py`
from . import setup_wallet


"""Initialize Redis for managing task"""
redis_conn = django_rq.get_connection('default')


"""API ENDPOINTS"""
@api.post("/initialize_transaction")
def initialize_transaction(request, payload: PayloadSchema):
    """
    API-ENDPOINT accessible for client to initialize sending transaction
    :param payload: encrypted payload with request data
    :param request: request object
    :return: JSON response
    """
    print(payload.__dict__)

    try:
        # TODO: DECRYPT REQUEST PAYLOAD

        # """ VALIDATE TX_ARGS BEFORE START """ #
        tx_args = Transaction.validate_tx_args(payload.amount, payload.address)
        if tx_args['error']: return tx_args

        # """ AUTHORIZE CONNECTION WITH TIME-LOCK FUNCTION """ #
        ip, address = connection_details(request, payload.address)
        authorized = connection_authorized(ip, address)
        if authorized['error']: return authorized

        # """ FIND AVAILABLE WALLET INSTANCE """ #
        wallet_instance = None

        # TODO: improve selecting wallet function models.get_wallet_status(wallet)
        while not wallet_instance:
            for wallet in WalletState.objects.filter(name__startswith=payload.wallet_type):
                print(wallet)
                if not wallet.is_locked:
                    wallet_instance = wallet
                    break
            if not wallet_instance:
                print(f">> No wallet available, re-try soon")
                time.sleep(1)

        # """ PREPARE TASK TO ENQUEUE """ #
        job_id = str(uuid.uuid4())
        queue = Queue(wallet_instance.name, default_timeout=800, connection=redis_conn)
        queue.enqueue(tasks.send_new_transaction, job_id=job_id, kwargs={
            'state_id': wallet_instance.id,
            'amount': payload.amount,
            'address': payload.address})

        return utils.response(SUCCESS, 'task enqueued', {'task_id': job_id, 'queue_len': queue.count})

    except Exception as e:
        return utils.response(ERROR, f'send task failed, {str(e)}')


@api.get("/finalize_transaction/tx_slate_id={tx_slate_id}&address={address}")
def finalize_transaction(request, tx_slate_id: str, address: str):
    """
    API-ENDPOINT accessible for client to initialize finalization of the transaction.
    :param address:
    :param tx_slate_id:
    :param request:
    :return:
    """
    try:
        ip, addr = connection_details(request, address)
        task = tasks.finalize_transaction.delay(
                wallet_cfg=wallet.config.essential(PASS_PATH),
                connection=(ip.address, addr.address),
                state_id=wallet.state.id,
                tx_slate_id=tx_slate_id)

        return utils.response(SUCCESS, 'task enqueued',
                              {'task_id': task.id, 'queue_len': queue.count})
    except Exception as e:
        return utils.response(ERROR, 'finalize_transaction task failed', str(e))


@api.get("/cancel_transaction/tx_slate_id={tx_slate_id}&address={address}")
def cancel_transaction(request, tx_slate_id: str, address: str):
    """
    :param address:
    :param request:
    :param tx_slate_id:
    :return:
    """
    ip, addr = connection_details(request, address)
    try:
        transaction = Transaction.objects.filter(tx_slate_id=tx_slate_id).first()

        if not transaction:
            return utils.response(ERROR, 'Transaction with given id does not exists')

        # We have to get wallet instance responsible for this transaction
        wallet_instance = WalletState.objects.filter(id=transaction.wallet_instance.id).first()

        # """ PREPARE TASK TO ENQUEUE """ #
        job_id = str(uuid.uuid4())
        queue = Queue(wallet_instance.name, default_timeout=800, connection=redis_conn)
        queue.enqueue(
            tasks.cancel_transaction,
            job_id=job_id,
            kwargs={'state_id': wallet_instance.id, 'tx_slate_id': tx_slate_id})

        # Update receiver lock status in database
        ip.is_now_locked()
        addr.is_now_locked()

        return utils.response(SUCCESS, 'task enqueued', {'task_id': job_id, 'queue_len': queue.count})

    except Exception as e:
        return utils.response(ERROR, 'cancel_transaction task failed', {e.__str__})


@api.get('/get_task/id={task_id}')
async def get_task(request, task_id: str):
    """
    API-ENDPOINT accessible for client to get status updates about queued task.
    :param request:
    :param task_id: UUID str, task ID
    :return: JSON response
    """
    try:
        task = Job.fetch(task_id, redis_conn)
        message = task.meta['message'] if 'message' in task.meta else 'No message'
        return {'status': task.get_status(), 'message': message, 'result': task.result}
    except Exception as err:
        return utils.response(ERROR, f'Task not found: {task_id} \n {str(err)}')


@api.get("/validate_address/address={address}")
def validate_address(request, address: str):
    print(address, len(address))
    return {'valid_': len(address.strip()) == 52}