from ninja import Router
from rq.job import Job
from rq import Queue
import django_rq

from .epic_sdk.wallet.wallet import Wallet
from .epic_sdk.utils import get_logger
import wallet.epic_sdk.utils as utils
from .default_settings import *
from . import tasks

from .models import Transaction, WalletState, connection_details, connection_authorized
from .schema import TxRequestSchema
from giveaway.models import Link

api = Router()
logger = get_logger()
PASS_PATH = 'Wallet/password'
first_run = True
try:
    """
    Initialize Server Wallet - Epic-Box Sender I,
    - executing outgoing transactions.
    """
    wallet = Wallet()
    NAME = "epicbox_1"
    wallet.state, _ = WalletState.objects.get_or_create(name=NAME)
    wallet.load_from_state()
    wallet.run_epicbox(callback=Transaction.updater_callback, force_run=True)


except Exception as e:
    print(e)
    logger.error(f"No database created yet, skipping initializing wallet")
    pass

"""Initialize Redis and Queue for managing task"""
redis_conn = django_rq.get_connection('default')
queue = Queue('epicbox', default_timeout=800, connection=redis_conn)


"""API ENDPOINTS"""
@api.post("/initialize_transaction")
def initialize_transaction(request, tx: TxRequestSchema):
    """
    API-ENDPOINT accessible for client to initialize sending transaction
    :param request: request object
    :param tx: transaction args (amount and address)
    :return: JSON response
    """
    try:
        # """ VALIDATE TRANSACTION REQUEST """ #
        tx_request = Link.validate(tx.code)

        if tx_request['error']:
            raise Exception('Invalid transaction request')

        tx_params = tx_request['result'].tx_params()

        if not tx_params['receiver_address']:
            tx_params['receiver_address'] = tx.receiver_address

        if tx_params['event'] == 'faucet':
            # """ AUTHORIZE CONNECTION WITH TIME-LOCK FUNCTION """ #
            ip, address = connection_details(request, tx.receiver_address)
            authorized = connection_authorized(ip, address)
            if authorized['error']: return authorized

        # """ PREPARE TASK TO ENQUEUE """ #
        task = tasks.send_new_transaction.delay(
            state_id=wallet.state.id,
            tx_params=tx_params,
            link_code=tx.code)

        return utils.response(SUCCESS, 'task enqueued', {'task_id': task.id, 'queue_len': queue.count})

    except Exception as e:
        return utils.response(ERROR, f'send task failed, {str(e)}')


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


# ====================================================================================

# @api.get("/finalize_transaction/tx_slate_id={tx_slate_id}&address={address}")
# def finalize_transaction(request, tx_slate_id: str, address: str):
#     """
#     API-ENDPOINT accessible for client to initialize finalization of the transaction.
#     :param address:
#     :param tx_slate_id:
#     :param request:
#     :return:
#     """
#     try:
#         ip, addr = connection_details(request, address)
#         task = tasks.finalize_transaction.delay(
#             wallet_cfg=wallet.config.essential(PASS_PATH),
#             connection=(ip.address, addr.address),
#             state_id=wallet.state.id,
#             tx_slate_id=tx_slate_id)
#
#         return utils.response(SUCCESS, 'task enqueued',
#                               {'task_id': task.id, 'queue_len': queue.count})
#     except Exception as e:
#         return utils.response(ERROR, 'finalize_transaction task failed', str(e))
#
#
# @api.get("/cancel_transaction/tx_slate_id={tx_slate_id}&address={address}")
# def cancel_transaction(request, tx_slate_id: str, address: str):
#     """
#     :param address:
#     :param request:
#     :param tx_slate_id:
#     :return:
#     """
#     print(tx_slate_id)
#     ip, addr = connection_details(request, address)
#     try:
#         task = tasks.cancel_transaction.delay(
#             wallet_cfg=wallet.config.essential(PASS_PATH),
#             state_id=wallet.state.id,
#             tx_slate_id=tx_slate_id)
#
#         # Update receiver lock status in database
#         print(ip.is_now_locked())
#         print(addr.is_now_locked())
#
#         return utils.response(SUCCESS, 'task enqueued', {'task_id': task.id, 'queue_len': queue.count})
#
#     except Exception as e:
#         return utils.response(ERROR, 'cancel_transaction task failed', {str(e)})
