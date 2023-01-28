from ninja import NinjaAPI
from rq.job import Job
from rq import Queue
import django_rq

from .epic_sdk.utils import get_logger
from . import tasks, get_secret_value
from .epic_sdk import Wallet, utils
from giverofepic import secrets
from .const_values import *

from .models import Transaction, WalletState, connection_details, connection_authorized
from .schema import TransactionSchema

api = NinjaAPI()
logger = get_logger()
PASS_PATH = 'Wallet/password'


try:
    """
    Initialize Server Wallet - Epic-Box Sender I, 
    - executing outgoing transactions.
    """
    NAME = "epic_box_1"
    wallet = Wallet(wallet_dir=secrets.WALLET_DIR, password=get_secret_value(PASS_PATH))
    wallet.state, _ = WalletState.objects.get_or_create(name=NAME)
except Exception as e:
    print(e)
    print(f"No database created yet, skipping initializing wallet")
    pass

"""Initialize Redis and Queue for managing task"""
redis_conn = django_rq.get_connection('default')
queue = Queue('epicbox', default_timeout=800, connection=redis_conn)


"""API ENDPOINTS"""
@api.post("/initialize_transaction")
def initialize_transaction(request, tx: TransactionSchema):
    """
    API-ENDPOINT accessible for client to initialize sending transaction
    :param request: request object
    :param tx: transaction args (amount and address)
    :return: JSON response
    """
    try:
        # """ VALIDATE TX_ARGS BEFORE START """ #
        tx_args = Transaction.validate_tx_args(tx.amount, tx.receiver_address)
        if tx_args['error']: return tx_args

        # """ AUTHORIZE CONNECTION WITH TIME-LOCK FUNCTION """ #
        ip, address = connection_details(request, tx.receiver_address)
        authorized = connection_authorized(ip, address)
        if authorized['error']: return authorized

        # """ PREPARE TASK TO ENQUEUE """ #
        task = tasks.send_new_transaction.delay(
                wallet_cfg=wallet.config.essential(PASS_PATH),
                state_id=wallet.state.id, tx=tx.dict())

        return utils.response(SUCCESS, 'task enqueued', {'task_id':  task.id, 'queue_len': queue.count})

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
    print(tx_slate_id)
    ip, addr = connection_details(request, address)
    try:
        task = tasks.cancel_transaction.delay(
                wallet_cfg=wallet.config.essential(PASS_PATH),
                state_id=wallet.state.id,
                tx_slate_id=tx_slate_id)

        # Update receiver lock status in database
        print(ip.is_now_locked())
        print(addr.is_now_locked())

        return utils.response(SUCCESS, 'task enqueued', {'task_id': task.id, 'queue_len': queue.count})

    except Exception as e:
        return utils.response(ERROR, 'cancel_transaction task failed', {str(e)})


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
    except Exception as e:
        return utils.response(ERROR, f'Task not found: {task_id} \n {str(e)}')


@api.get("/validate_address/address={address}")
def validate_address(request, address: str):
    print(address, len(address))
    return {'valid_': len(address.strip()) == 52}