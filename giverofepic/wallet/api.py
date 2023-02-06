import pickle

from asgiref.sync import sync_to_async
from ninja import NinjaAPI

from .models import Transaction, WalletManager, CustomAPIKeyAuth
from .epic_sdk.utils import get_logger
from .schema import PayloadSchema
from faucet.models import Client
from .default_settings import *
from .epic_sdk import utils
from . import signals
from . import tasks


api = NinjaAPI()
auth = CustomAPIKeyAuth()
logger = get_logger()


# TODO: change finalize workflow (use listeners instead triggering event)
""" Initialize multiple wallet manager (WalletPool)"""
WalletPool = WalletManager()


"""API ENDPOINTS"""
@api.post("/request_transaction", auth=auth)
async def initialize_transaction(request, payload: PayloadSchema):
    """
    API-ENDPOINT accessible for client to initialize sending transaction
    :param payload: encrypted payload with request data
    :param request: request object
    :return: JSON response
    """
    print(payload.__dict__)
    print(request.POST)

    # try:
    # TODO: DECRYPT REQUEST PAYLOAD
    # TODO: AUTHORIZE WITH API_KEY

    # """ VALIDATE REQUEST PAYLOAD BEFORE START """ #
    tx_args = Transaction.validate_tx_args(payload.amount, payload.address)
    if tx_args['error']: return tx_args

    # """ AUTHORIZE CLIENT CONNECTION (I.E. TIME-LOCK FUNCTION )""" #
    client = await Client.from_request(request, payload.address)
    if not await client.is_allowed(): return await client.receiver.locked_msg()

    # """ FIND AVAILABLE WALLET INSTANCE """ #
    wallet_instance = await sync_to_async(WalletPool.get_available_wallet)(wallet_type=payload.wallet_type)

    if not wallet_instance:
        message = f"Can't process your request right now, please try again later."
        return utils.response(ERROR, message)

    # """ PREPARE TASK TO ENQUEUE """ #
    args = (payload.amount, payload.address, wallet_instance, client)
    task_id, queue = WalletPool.enqueue_task(wallet_instance, tasks.send_new_transaction, *args)

    return utils.response(SUCCESS, 'task successfully enqueued', {'task_id': task_id, 'queue_len': queue.count})

    # except Exception as e:
    #     return utils.response(ERROR, f'send task failed, {str(e)}')


@api.get("/cancel_transaction/tx_slate_id={tx_slate_id}")
async def cancel_transaction(request, tx_slate_id: str):
    """
    :param request:
    :param tx_slate_id:
    :return:
    """
    try:
        # Get transaction object
        transaction = await Transaction.objects.filter(tx_slate_id=tx_slate_id).afirst()
        if not transaction: return utils.response(ERROR, 'Transaction with given id does not exists')

        # """ ENQUEUE TASK """ #
        kwargs = {'tx': pickle.dumps(transaction)}
        task_id, queue = WalletPool.enqueue_task(transaction.sender, tasks.cancel_transaction, **kwargs)
        return utils.response(SUCCESS, 'task successfully enqueued', {'task_id': task_id, 'queue_len': queue.count})

    except Exception as e:
        print(e)
        return utils.response(ERROR, 'cancel_transaction task failed')


@api.get("/get_pending_slates")
def get_pending_slates(request):
    WalletPool.get_pending_slates()
    # print(request.POST)


@api.get("/rescan_and_clean_transactions")
def rescan_and_clean_transactions(request):
    wallet_instance = WalletPool.get_wallet(name='faucet_1')
    WalletPool.enqueue_task(
        wallet_instance=wallet_instance,
        target_func=tasks.rescan_and_clean_transactions,
        **{'wallet': wallet_instance})


@api.get('/get_task/id={task_id}')
async def get_task(request, task_id: str):
    """
    API-ENDPOINT accessible for client to get status updates about queued task.
    :param request:
    :param task_id: UUID str, task ID
    :return: JSON response
    """
    try:
        return WalletPool.get_task(task_id)
    except Exception as err:
        return utils.response(ERROR, f'Task not found: {task_id} \n {str(err)}')
