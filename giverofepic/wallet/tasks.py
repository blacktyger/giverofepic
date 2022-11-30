import json

from rq import get_current_job
from django.db.models import Q
from rq.decorators import job
import django_rq
import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "giverofepic.settings")
django.setup()

from .models import WalletState, get_wallet_status, Transaction, update_connection_details
from .const_values import SUCCESS, ERROR
from .schema import TransactionSchema
from .logger_ import get_logger
from .epic_sdk import Wallet
from .epic_sdk import utils


logger = get_logger()


"""Initialize Queue for managing task"""
redis_conn = django_rq.get_connection('default')


@job('epicbox', redis_conn, timeout=30)
def finalize_transaction(wallet_cfg: dict, state_id: str):
    logger.info(f">> start working on task {get_current_job().id}")

    wallet = Wallet(**wallet_cfg)
    wallet.state = WalletState.objects.get(id=state_id)

    # """ GET OR WAIT FOR UNLOCKED INSTANCE """ #
    is_unlocked = get_wallet_status(wallet)
    if is_unlocked['error']: return is_unlocked

    # wallet.state.lock()  # Lock the wallet instance

    # DEFINE FUNCTION VARIABLES
    to_process = []
    processed = []
    to_post = []
    posted = 0

    logger.info(">> Getting unprocessed slates from epic-box server..")
    encrypted_slates = wallet.get_tx_slates()
    w_addr = wallet.epicbox.address

    logger.info(">> Getting slates from local database..")
    txs = Transaction.objects.filter(
        Q(archived=False) and (Q(receiver_address=w_addr) | Q(sender_address=w_addr)))

    # LIST OF TX_IDs FROM WALLET INSTANCE DB
    txs_ids = [str(tx.tx_slate_id) for tx in txs]

    # Filter new slates and append to list
    logger.info(f">> Start decrypting {len(encrypted_slates)} slates")
    for encrypted_string in encrypted_slates:
        decrypted_slate = wallet.decrypt_tx_slates([encrypted_string])[0]
        slate_string, address = decrypted_slate
        db_tx, network_slate = json.loads(slate_string)
        incoming_slate_tx_id = json.loads(db_tx)[0]['tx_slate_id']

        # Iterate through slates associated with this wallet instance,
        # either 'init_tx_slate' or 'response_tx_slate', this wallet as sender
        if incoming_slate_tx_id in txs_ids:
            tx_ = txs.get(tx_slate_id=incoming_slate_tx_id)

            # Save encrypted slate string to remove it later from epicbox server
            tx_.encrypted_slate = encrypted_string

            if 'initialized' in tx_.status:
                logger.info(f">> {tx_} ready to process")
                to_process.append(json.loads(slate_string))

            elif 'finalized' in tx_.status:
                logger.info(f">> {tx_} already finalized")
                logger.info(wallet.post_delete_tx_slate(receiving_address=w_addr, slate=encrypted_string))

            elif 'finished' in tx_.status:
                logger.info(f">> {tx_} already finished")
                tx_.archived = True
                logger.info(wallet.post_delete_tx_slate(receiving_address=w_addr, slate=encrypted_string))

                # wallet.post_cancel_transaction(receiving_address=w_addr, tx_slate_id=incoming_slate_tx_id)
                # wallet.post_delete_canceled_tx_slates(receiving_address=w_addr, tx_slate_id=incoming_slate_tx_id)

            tx_.save()
        # Iterate through slates not known to this wallet instance,
        # most likely TxReceived type of slate, this wallet as receiver
        else:
            pass
            # logger.info(wallet.post_delete_tx_slate(receiving_address=w_addr, slate=encrypted_string))

    # Process filtered slates
    logger.info(f">> Start processing {len(to_process)} slates..")
    processed += wallet.process_tx_slates(to_process)

    if not processed:
        wallet.state.unlock()  # Release the wallet
        return utils.response(ERROR, "No slates processed")

    for tx_ in Transaction.objects.filter(status='initialized', archived=False):
        tx_.status = 'finalized'
        tx_.save()
        to_post.append(tx_)

    # Post finalized transactions to the node (network)
    logger.info(f">> Start sending {len(to_post)} transactions..")
    for ready_tx in to_post:
        logger.info(f">> sending {ready_tx}...")
        post_tx = wallet.post_transaction(tx_slate_id=str(ready_tx.tx_slate_id))
        logger.info(post_tx)

        if post_tx:
            ready_tx.status = 'finished'
            ready_tx.archived = True
            ready_tx.save()
            logger.info(f">> {ready_tx} posted, finished and archived successfully")
            posted += 1
        else:
            logger.info(f">> {ready_tx} failed to post, ")

    report = {
        "slates_received": len(encrypted_slates),
        "slates_decrypted": len(to_process),
        "slates_processed": len(to_post),
        "txs_finished": posted
        }

    wallet.state.unlock()  # Release the wallet instance

    return utils.response(SUCCESS, 'success', report)


@job('epicbox', redis_conn, timeout=30)
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

    logger.info(f">> start working on task {get_current_job().id}")
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
