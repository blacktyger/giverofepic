from asgiref.sync import sync_to_async
from ninja import Router

from .schema import TransactionPayloadSchema, CancelPayloadSchema
from faucet.models import Client, SecureRequest
from giverofepic.tools import CustomAPIKeyAuth
from .models import Transaction, WalletManager
from .epic_sdk.utils import get_logger
from .default_settings import *
from .epic_sdk import utils
from . import signals
from . import tasks


api = Router()
auth = CustomAPIKeyAuth()
logger = get_logger()


# TODO: change finalize workflow (use listeners instead triggering event)
""" Initialize multiple wallet's manager (WalletPool)"""
WalletPool = WalletManager()


"""API ENDPOINTS"""
@api.post("/request_transaction", auth=auth)
async def initialize_transaction(request, payload: TransactionPayloadSchema):
    """
    API-ENDPOINT for client to request transaction
    :param payload: encrypted payload with transaction data
    :param request: Request object
    :return: JSON response

    payload = {
          'amount': 0.01,
          'event': 'faucet',
          'address': 'esWenAmhSg9KEmEHMf5JtcuhacVteHHHekT3Xg4yyeoNVXVwo7AW'
    }
    """
    print(request.auth)
    try:
        # """ VALIDATE TRANSACTION PAYLOAD """ #
        tx_args = Transaction.validate_tx_args(payload.dict())
        if tx_args['error']: return tx_args

        # """ AUTHORIZE CLIENT CONNECTION (I.E. TIME-LOCK FUNCTION )""" #
        client = await Client.from_request(request, payload.address)
        if not await client.is_allowed(): return await client.receiver.locked_msg()

        # """ FIND AVAILABLE WALLET INSTANCE """ #
        wallet_instance = await WalletPool.get_available_wallet(wallet_type=payload.event)
        if not wallet_instance: return utils.response(ERROR, f"Can't process your request right now, please try again later.")

        # """ ENQUEUE WALLET TASK """ #
        args = (payload.amount, payload.address, wallet_instance, client)
        task_id, queue = WalletPool.enqueue_task(wallet_instance, tasks.send_new_transaction, *args)

        return utils.response(SUCCESS, 'task successfully enqueued', {'task_id': task_id, 'queue_len': queue.count})

    except Exception as e:
        return utils.response(ERROR, f'send task failed, {str(e)}')


@api.post("/cancel_transaction", auth=auth)
async def cancel_transaction(request, payload: CancelPayloadSchema):
    """
    API-ENDPOINT for client to request transaction cancellation, requires tx_slate_id
    :param request: Request object
    :param payload: transaction slate id
    :return: JSON Response
    """
    print(request.auth)
    print(request.auth.__dict__)

    try:
        # Get transaction object
        transaction = await Transaction.objects.filter(tx_slate_id=payload.tx_slate_id).afirst()
        if not transaction: return utils.response(ERROR, 'Transaction with given id does not exists')

        # Enqueue task
        wallet_instance = await sync_to_async(lambda: transaction.sender)()
        task_id, queue = WalletPool.enqueue_task(wallet_instance, tasks.cancel_transaction, *(transaction, ))
        return utils.response(SUCCESS, 'task successfully enqueued', {'task_id': task_id, 'queue_len': queue.count})

    except Exception as e:
        logger.error(e)
        return utils.response(ERROR, 'cancel_transaction task failed')


@api.post("/encrypt_data", auth=auth)
def encrypt_transaction_data(request, payload: TransactionPayloadSchema):
    """Endpoint for tests, in production client is responsible to encrypt the payload."""
    print(payload.json())
    return SecureRequest(request).encrypt(payload.json())


@api.post("/decrypt_data/data={encrypted_data}", auth=auth)
def decrypt_data(request, encrypted_data: str):
    return SecureRequest(request).decrypt(encrypted_data)


@api.get("/get_pending_slates")
def get_pending_slates(request):
    WalletPool.get_pending_slates()
    # print(request.POST)


@api.get("/rescan_and_clean_transactions")
def rescan_and_clean_transactions(request):
    """Endpoint for tests, trigger single wallet instance transaction clean-up (remove old not finished)."""
    wallet_instance = WalletPool.get_wallet(name='faucet_1')
    WalletPool.enqueue_task(
        wallet_instance=wallet_instance,
        target_func=tasks.rescan_and_clean_transactions,
        **{'wallet': wallet_instance}
        )


@api.get('/get_task/id={task_id}')
async def get_task(request, task_id: str):
    """
    API-ENDPOINT accessible for client to get status updates about queued task.
    :param request: Request object
    :param task_id: UUID str, task ID
    :return: JSON response
    """
    try:
        return WalletPool.get_task(task_id)
    except Exception as err:
        return utils.response(ERROR, f'Task not found: {task_id} \n {str(err)}')
