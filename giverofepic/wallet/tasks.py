from django.utils import timezone
from rq import get_current_job
from rq.decorators import job
import django_rq
import django
import os

# Must be called before imports from Django components

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "giverofepic.settings")
django.setup()

from .models import WalletState, get_wallet_status, Transaction, update_connection_details
from .default_settings import SUCCESS, ERROR
from .epic_sdk import Wallet, utils
from giveaway.models import Link
from .logger_ import get_logger


"""Initialize Logger"""
logger = get_logger()

"""Initialize Queue for managing task"""
redis_conn = django_rq.get_connection('default')


@job('epicbox', redis_conn, timeout=30)
def send_new_transaction(tx_params: dict, state_id: str, link_code: str):
    """
    :param tx_params: dict
    :param link_code: str
    :param state_id: str
    :return: dict
    """
    this_task = get_current_job()
    logger.info(f">> start working on task send_new_transaction {this_task.id}")

    # """ VALIDATE TRANSACTION PARAMS """ #
    tx_args = Transaction.validate_tx_args(**tx_params)
    if tx_args['error']: return tx_args

    wallet = Wallet()
    wallet.state = WalletState.objects.get(id=state_id)
    wallet = wallet.load_from_state()

    # """ GET OR WAIT FOR UNLOCKED INSTANCE """ #
    is_unlocked = get_wallet_status(wallet)

    if is_unlocked['error']:
        this_task.meta['message'] = f"Can't process your request right now, please try again later."
        this_task.save_meta()
        return is_unlocked

    # TODO: Uncomment for production
    # wallet.state.lock()  # Lock the wallet instance

    # """ MAKE SURE WALLET BALANCE IS SUFFICIENT """ #
    if not wallet.is_balance_enough(tx_params['amount'])[0]:
        logger.warning('not enough balance')
        this_task.meta['message'] = f"Not enough balance, please try again later."
        this_task.save_meta()
        return utils.response(ERROR, wallet.state.error_msg())

    ## >> Prepare tx_args and transaction slate
    tx_params['wallet_id'] = state_id
    tx_params['status'] = 'initialized'
    print(tx_params)

    try:
        ## >> Create new Transaction object
        transaction = Transaction.objects.create(**tx_params)

        ## >> Send the transaction
        response_ = wallet.send_transaction(
            method='epicbox',
            address=transaction.receiver_address,
            amount=transaction.amount,
            )

        if not response_['error']:
            # TODO: Update frontend feedback
            # Update transaction record
            # print(response_)
            transaction.update_from_slate(response_['result'])
            transaction.update_status('pending')

            # Update claiming link params
            # Link.objects.filter(code=link_code).first().update_params(**{
            #     "claim_date": timezone.now(),
            #     "claimed": True,
            #     "address": transaction.receiver_address
            #     })

            response = utils.response(SUCCESS, 'post tx success', {'tx_slate_id': transaction.tx_slate_id})
        else:
            response = utils.response(ERROR, f'post tx failed')

    except Exception as e:
        # wallet.cancel_tx_slate(slate=init_tx_slate)
        response = utils.response(ERROR, f"post tx failed and canceled, {str(e)}")

    wallet.state.unlock()  # Release wallet

    logger.info(response)
    return response


# =================================================================

# @job('epicbox', redis_conn, timeout=30)
# def cancel_transaction(wallet_cfg: dict, state_id: str, tx_slate_id: str):
#     wallet_cfg['password'] = get_secret_value(wallet_cfg['password'])
#     wallet = Wallet(**wallet_cfg)
#     this_task = get_current_job()
#     wallet.state = WalletState.objects.get(id=state_id)
#
#     logger.info(f">> start working on task cancel_transaction {this_task.id}")
#
#     # """ GET OR WAIT FOR UNLOCKED INSTANCE """ #
#     is_unlocked = get_wallet_status(wallet)
#     if is_unlocked['error']:
#         this_task.meta['message'] = f"Wallet locked, cancel failed"
#         this_task.save_meta()
#         return is_unlocked
#
#     transaction = Transaction.objects.filter(tx_slate_id=tx_slate_id).first()
#     if transaction:
#
#         # Cancel in local wallet history
#         logger.info(f"Local wallet transaction: {wallet.cancel_tx_slate(tx_slate_id=tx_slate_id)}")
#
#         print('try to delete slate')
#         logger.info(wallet.post_delete_tx_slate(receiving_address=transaction.sender_address,
#                                                 slate=transaction.encrypted_slate))
#
#         # Cancel in epic-box server
#         cancel = wallet.post_cancel_transaction(
#             receiving_address=transaction.receiver_address,
#             tx_slate_id=tx_slate_id)
#         logger.info(f"Epicbox slate canceled: "
#                     f"{cancel['status'] if 'status' in cancel else 'failed'}")
#
#         transaction.archived = True
#         transaction.status = 'cancelled'
#         transaction.save()
#
#         return utils.response(SUCCESS, 'transaction canceled')
#
#
# @job('epicbox', redis_conn, timeout=30, retry=Retry(max=1, interval=2))
# def finalize_transaction(wallet_cfg: dict, state_id: str, tx_slate_id: str, connection: tuple):
#     sys.tracebacklimit = 1
#     logger.info(f">> start working on task finalize_transaction {get_current_job().id}")
#
#     wallet_cfg['password'] = get_secret_value(wallet_cfg['password'])
#     wallet = Wallet(**wallet_cfg)
#     wallet.state = WalletState.objects.get(id=state_id)
#
#     # """ GET OR WAIT FOR UNLOCKED INSTANCE """ #
#     is_unlocked = get_wallet_status(wallet)
#     if is_unlocked['error']: return is_unlocked
#
#     # TODO: Uncomment for production
#     # wallet.state.lock()  # Lock the wallet instance
#
#     # DEFINE FUNCTION VARIABLES
#     is_requested_tx = False
#     to_process = []
#     processed = []
#     to_post = []
#     posted = 0
#
#     logger.info(">> Getting unprocessed slates from epic-box server..")
#     encrypted_slates = wallet.get_tx_slates()
#     w_addr = wallet.epicbox.address
#
#     logger.info(">> Getting slates from local database..")
#     txs = Transaction.objects.filter(
#         Q(archived=False) and (Q(receiver_address=w_addr) | Q(sender_address=w_addr)))
#
#     # LIST OF TX_IDs FROM WALLET INSTANCE DB
#     txs_ids = [str(tx.tx_slate_id) for tx in txs]
#
#     # CONFIRM tx_slate_id BELONGS TO THIS WALLET AND IT IS NOT FINISHED ALREADY
#     if tx_slate_id not in txs_ids:
#         return utils.response(ERROR, "Transaction not found in the server wallet.")
#
#     # Filter new slates and append to list
#     logger.info(f">> Start decrypting {len(encrypted_slates)} slates")
#
#     for encrypted_string in encrypted_slates:
#         decrypted_slate = wallet.decrypt_tx_slates([encrypted_string])[0]
#         slate_string, address = decrypted_slate
#         db_tx, network_slate = json.loads(slate_string)
#         incoming_slate_tx_id = json.loads(db_tx)[0]['tx_slate_id']
#
#         # Confirm that requested transaction id is received
#         if incoming_slate_tx_id in tx_slate_id: is_requested_tx = True
#
#         # Iterate through slates associated with this wallet instance,
#         # either 'init_tx_slate' or 'response_tx_slate', this wallet as sender
#         if incoming_slate_tx_id in txs_ids:
#             tx_ = txs.get(tx_slate_id=incoming_slate_tx_id)
#
#             # Save encrypted slate string to remove it later from epicbox server
#             tx_.encrypted_slate = encrypted_string
#
#             if 'initialized' in tx_.status:
#                 logger.info(f">> {tx_} ready to process")
#                 to_process.append(json.loads(slate_string))
#
#             elif 'finalized' in tx_.status:
#                 logger.info(f">> {tx_} already finalized")
#                 logger.info(wallet.post_delete_tx_slate(receiving_address=w_addr, slate=encrypted_string))
#
#             elif 'finished' in tx_.status:
#                 logger.info(f">> {tx_} already finished")
#                 tx_.archived = True
#                 logger.info(wallet.post_delete_tx_slate(receiving_address=w_addr, slate=encrypted_string))
#
#             elif 'cancelled' in tx_.status:
#                 logger.info(f">> {tx_} already cancelled")
#                 tx_.archived = True
#                 logger.info(wallet.post_delete_tx_slate(receiving_address=w_addr, slate=encrypted_string))
#
#             tx_.save()
#         # TODO
#         # Iterate through slates not known to this wallet instance,
#         # most likely TxReceived type of slate, this wallet as receiver
#         else:
#             pass
#             # logger.info(wallet.post_delete_tx_slate(receiving_address=w_addr, slate=encrypted_string))
#
#     # Process filtered slates
#     logger.info(f">> Start processing {len(to_process)} slates..")
#     processed += wallet.process_tx_slates(to_process)
#
#     if not processed:
#         sys.tracebacklimit = 0
#         wallet.state.unlock()  # Release the wallet
#         raise Exception('requested tx not found, re-try') from None
#         # return utils.response(ERROR, "No slates processed")
#
#     for tx_ in Transaction.objects.filter(status='initialized', archived=False):
#         tx_.status = 'finalized'
#         tx_.save()
#         to_post.append(tx_)
#
#     # Post finalized transactions to the node (network)
#     logger.info(f">> Start sending {len(to_post)} transactions..")
#     for ready_tx in to_post:
#         logger.info(f">> sending {ready_tx}...")
#         post_tx = wallet.post_transaction(tx_slate_id=str(ready_tx.tx_slate_id))
#         logger.info(post_tx)
#
#         if post_tx:
#             ready_tx.status = 'finished'
#             logger.info(f">> {ready_tx} posted, finished and archived successfully")
#             posted += 1
#             # Update connection timestamps for time-lock function
#             logger.info(update_connection_details(*connection))
#         else:
#             ready_tx.status = 'cancelled'
#             logger.info(f">> {ready_tx} failed to post (cancelled)")
#
#         ready_tx.archived = True
#         ready_tx.save()
#
#     report = {
#         "is_requested_tx": is_requested_tx,
#         "slates_received": len(encrypted_slates),
#         "slates_decrypted": len(to_process),
#         "slates_processed": len(to_post),
#         "txs_finished": posted
#         }
#
#     wallet.state.unlock()  # Release the wallet instance
#     message = f'confirmed tx requested by user: {is_requested_tx}'
#     return utils.response(SUCCESS, message, report)
