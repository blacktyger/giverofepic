import pickle

from rq import get_current_job
import django_rq
import django
import json
import sys
import os

# Must be called before imports from Django components
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "giverofepic.settings")
django.setup()

from .models import Transaction, update_connection_details, WalletManager
from .default_settings import SUCCESS, ERROR
from .epic_sdk import Wallet, utils
from .logger_ import get_logger
from . import get_secret_value


"""Initialize Logger"""
logger = get_logger()

"""Initialize Queue for managing task"""
redis_conn = django_rq.get_connection('default')


def send_new_transaction(*args):
    this_task = get_current_job()
    logger.info(f">> start working on task send_new_transaction {this_task.id}")

    amount, address, wallet_instance = [pickle.loads(v) for v in args]
    print(amount, address, wallet_instance)
    wallet_instance.lock()  # Lock the wallet instance

    # Initialize Wallet class from PythonSDK
    wallet = Wallet(
        wallet_dir=wallet_instance.wallet_dir,
        password=get_secret_value(wallet_instance.password_path))

    # """ MAKE SURE WALLET BALANCE IS SUFFICIENT """ #
    balance = wallet.is_balance_enough(amount)

    if balance is None:
        logger.warning('not enough balance')
        this_task.meta['message'] = f"Not enough balance, please try again later."
        this_task.save_meta()
        wallet_instance.unlock()  # Release wallet
        return utils.response(ERROR, this_task.meta['message'])

    wallet_instance.update_balance(balance)

    # """ START CREATING NEW TRANSACTION """ #
    ## >> Create TX slate
    init_tx_slate = wallet.create_tx_slate(amount=amount)

    ## >> Parse tx_args and prepare transaction slate
    try:
        tx_args = Transaction.parse_init_slate(init_tx_slate)
        tx_args['receiver_address'] = address
        tx_args['wallet_instance'] = wallet_instance
        tx_args['sender_address'] = wallet.epicbox.address
        tx_args['status'] = "initialized"
        tx_args['amount'] = amount

        ## >> Create new Transaction object
        transaction = Transaction.objects.create(**tx_args)
        response_ = wallet.post_tx_slate(address, init_tx_slate)

        if response_:
            wallet_instance.last_transaction = transaction
            wallet_instance.save()
            response = utils.response(SUCCESS, 'post tx success', {'tx_slate_id': transaction.tx_slate_id})
        else:
            response = utils.response(ERROR, f'post tx failed')

    except Exception as e:
        wallet.cancel_tx_slate(slate=init_tx_slate)
        response = utils.response(ERROR, f"post tx failed and canceled, {str(e)}")

    wallet_instance.unlock()  # Release wallet
    return response


def finalize_transaction(*args):
    sys.tracebacklimit = 1
    logger.info(f">> start working on task finalize_transaction {get_current_job().id}")

    tx_, wallet_instance, connection = [pickle.loads(v) for v in args]
    tx_slate_id = str(tx_.tx_slate_id)

    # Initialize Wallet class from PythonSDK
    wallet = Wallet(
        wallet_dir=wallet_instance.wallet_dir,
        password=get_secret_value(wallet_instance.password_path))

    # DEFINE FUNCTION VARIABLES
    to_process = []
    processed = []
    to_post = []
    posted = 0

    logger.info(">> Getting unprocessed slates from epic-box server..")
    encrypted_slates = wallet.get_tx_slates()
    w_addr = wallet.epicbox.address

    logger.info(f">> Start decrypting {len(encrypted_slates)} slates")
    for encrypted_string in encrypted_slates:
        decrypted_slate = wallet.decrypt_tx_slates([encrypted_string])[0]
        slate_string, address = decrypted_slate
        db_tx, network_slate = json.loads(slate_string)
        decrypted_slate_id = json.loads(db_tx)[0]['tx_slate_id']

        # Confirm that requested transaction id is received
        if decrypted_slate_id in tx_slate_id:
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

            elif 'cancelled' in tx_.status:
                logger.info(f">> {tx_} already cancelled")
                tx_.archived = True
                logger.info(wallet.post_delete_tx_slate(receiving_address=w_addr, slate=encrypted_string))

            tx_.save()
            break

    # Process filtered slates
    logger.info(f">> Start processing {len(to_process)} slates..")
    processed += wallet.process_tx_slates(to_process)

    if not processed:
        sys.tracebacklimit = 0
        wallet_instance.unlock()  # Release the wallet
        raise Exception('requested tx not found, re-try') from None
        # return utils.response(ERROR, "No slates processed")

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
            logger.info(f">> {ready_tx} posted, finished and archived successfully")
            posted += 1
            # Update connection timestamps for time-lock function
            logger.info(update_connection_details(*connection))
        else:
            ready_tx.status = 'cancelled'
            logger.info(f">> {ready_tx} failed to post (cancelled)")

        ready_tx.archived = True
        ready_tx.save()

    report = {
        "is_requested_tx": True,
        "slates_received": len(encrypted_slates),
        "slates_decrypted": len(to_process),
        "slates_processed": len(to_post),
        "txs_finished": posted
        }

    wallet_instance.unlock()  # Release the wallet instance
    message = f'confirmed tx requested by user: {report["is_requested_tx"]}'
    return utils.response(SUCCESS, message, report)


def cancel_transaction(*args):
    logger.info(f">> start working on task cancel_transaction {get_current_job().id}")
    transaction, wallet_instance, connection = [pickle.loads(v) for v in args]
    tx_slate_id = str(transaction.tx_slate_id)

    # Initialize Wallet class from PythonSDK
    wallet = Wallet(
        wallet_dir=wallet_instance.wallet_dir,
        password=get_secret_value(wallet_instance.password_path))
    wallet_instance.lock()  # Lock the wallet instance

    # Cancel in local wallet history
    logger.info(f"Local wallet transaction: {wallet.cancel_tx_slate(tx_slate_id=tx_slate_id)}")
    wallet.post_delete_tx_slate(receiving_address=transaction.sender_address, slate=transaction.encrypted_slate)

    # Cancel in epic-box server
    cancel = wallet.post_cancel_transaction(
        receiving_address=transaction.receiver_address,
        tx_slate_id=tx_slate_id)
    logger.info(f"Epicbox slate canceled: "
                f"{cancel['status'] if 'status' in cancel else 'failed'}")

    wallet_instance.unlock()  # Release wallet
    transaction.archived = True
    transaction.status = 'cancelled'
    transaction.save()

    # Update receiver lock status in database
    ip, addr = connection
    ip.is_now_locked()
    addr.is_now_locked()

    return utils.response(SUCCESS, 'transaction canceled')
