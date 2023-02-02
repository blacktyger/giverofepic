import pickle
import uuid

from rq.job import Job, Retry
from ninja import NinjaAPI
from rq import Queue
import django_rq

from .models import Transaction, connection_details, connection_authorized, WalletManager
from .epic_sdk.utils import get_logger
from .schema import PayloadSchema
from .default_settings import *
from .epic_sdk import utils
from . import tasks

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
        # TODO: AUTHORIZE WITH API_KEY

        # """ VALIDATE TX_ARGS BEFORE START """ #
        tx_args = Transaction.validate_tx_args(payload.amount, payload.address)
        if tx_args['error']: return tx_args

        # """ AUTHORIZE CONNECTION WITH TIME-LOCK FUNCTION """ #
        ip, address = connection_details(request, payload.address)
        authorized = connection_authorized(ip, address)
        if authorized['error']: return authorized

        # """ FIND AVAILABLE WALLET INSTANCE """ #
        wallet_instance = WalletManager().get_available_wallet(wallet_type=payload.wallet_type)

        if not wallet_instance:
            message = f"Can't process your request right now, please try again later."
            return utils.response(ERROR, message)

        # """ PREPARE TASK TO ENQUEUE """ #
        job_id = str(uuid.uuid4())
        args = tuple(pickle.dumps(v) for v in [payload.amount, payload.address, wallet_instance])
        queue = Queue(wallet_instance.name, default_timeout=800, connection=redis_conn)
        queue.enqueue(tasks.send_new_transaction, job_id=job_id, args=args)

        return utils.response(SUCCESS, 'task successfully enqueued', {'task_id': job_id, 'queue_len': queue.count})

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
        # We have to get transaction and wallet instance objects
        wallet_instance, transaction = WalletManager().get_wallet_by_tx(tx_slate_id=tx_slate_id)

        if not transaction:
            return utils.response(ERROR, 'Transaction with given id does not exists')

        # """ PREPARE TASK TO ENQUEUE """ #
        job_id = str(uuid.uuid4())
        args = tuple(pickle.dumps(v) for v in [transaction, wallet_instance, connection_details(request, address)])
        queue = Queue(wallet_instance.name, default_timeout=800, connection=redis_conn)
        queue.enqueue(tasks.finalize_transaction, job_id=job_id, args=args, retry=Retry(max=1, interval=3))

        return utils.response(SUCCESS, 'task successfully enqueued', {'task_id': job_id, 'queue_len': queue.count})

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
    try:
        # We have to get transaction and wallet instance objects
        wallet_instance, transaction = WalletManager().get_wallet_by_tx(tx_slate_id=tx_slate_id)

        if not transaction:
            return utils.response(ERROR, 'Transaction with given id does not exists')

        # """ PREPARE TASK TO ENQUEUE """ #
        job_id = str(uuid.uuid4())
        args = tuple(pickle.dumps(v) for v in [transaction, wallet_instance, connection_details(request, address)])
        queue = Queue(wallet_instance.name, default_timeout=800, connection=redis_conn)
        queue.enqueue(tasks.cancel_transaction, job_id=job_id, args=args)

        return utils.response(SUCCESS, 'task successfully enqueued', {'task_id': job_id, 'queue_len': queue.count})

    except Exception as e:
        print(e)
        return utils.response(ERROR, 'cancel_transaction task failed')


@api.get('/get_task/id={task_id}')
async def get_task(request, task_id: str):
    """
    API-ENDPOINT accessible for client to get status updates about queued task.
    :param request:
    :param task_id: UUID str, task ID
    :return: JSON response
    """
    # try:
    task = Job.fetch(task_id, redis_conn)
    message = task.meta['message'] if 'message' in task.meta else 'No message'
    return {'status': task.get_status(), 'message': message, 'result': task.result}

    # except Exception as err:
    #     return utils.response(ERROR, f'Task not found: {task_id} \n {str(err)}')
