import time

import django
import django_rq
from rq.decorators import job

django.setup()

from .models import WalletState, get_wallet_status, Transaction, update_connection_details
from .const_values import SUCCESS, ERROR
from .schema import TransactionSchema
from .logger_ import get_logger
from .epic_sdk import Wallet
from .epic_sdk import utils


logger = get_logger()
logger.critical('here1')


def send_success(job, connection, result, *args, **kwargs):
    logger.critical(job.return_value)
    return job.return_value


"""Initialize Queue for managing task"""
queue = django_rq.get_queue('default', default_timeout=800)
redis_conn = django_rq.get_connection('default')


@job('default', redis_conn, timeout=30)
def send_new_transaction(tx: dict, wallet_cfg: dict, connection: tuple, state_id: str):
    """
    :param tx:
    :param wallet_cfg:
    :param connection:
    :param state_id:
    :return:
    """
    tx = TransactionSchema.parse_obj(tx)
    wallet = Wallet(**wallet_cfg)
    wallet.state = WalletState.objects.get(id=state_id)

    logger.info(f">> start working on task")
    # """ GET OR WAIT FOR UNLOCKED INSTANCE """ #
    is_unlocked = get_wallet_status(wallet)
    if is_unlocked['error']: return is_unlocked

    # wallet.state.lock()  # Lock the wallet instance

    # """ MAKE SURE WALLET BALANCE IS SUFFICIENT """ #
    if not wallet.is_balance_enough(tx.amount):
        logger.warning('not enough balance')
        return utils.response(ERROR, wallet.state.error_msg())

    # """ START CREATING NEW TRANSACTION """ #
    ## >> Create TX slate
    init_tx_slate = wallet.create_tx_slate(amount=tx.amount)

    ## >> Parse tx_args and prepare transaction slate
    try:
        tx_args = Transaction.parse_init_slate(init_tx_slate)
        tx_args['receiver_address'] = tx.receiver_address
        tx_args['sender_address'] = wallet.epicbox.address
        tx_args['status'] = "initialized"
        tx_args['amount'] = tx.amount

        ## >> Create new Transaction object
        transaction = Transaction.objects.create(**tx_args)
        post_tx = wallet.post_tx_slate(tx.receiver_address, init_tx_slate)

        if post_tx:
            # Update connection timestamps for time-lock function
            logger.info(update_connection_details(*connection))
            response = utils.response(SUCCESS, 'post tx success', transaction.tx_slate_id)
        else:
            response = utils.response(ERROR, f'post tx failed')

    except Exception as e:
        wallet.cancel_tx_slate(slate=init_tx_slate)
        response = utils.response(ERROR, f"post tx failed and canceled, {str(e)}")

    wallet.state.unlock()  # Release wallet

    return response
