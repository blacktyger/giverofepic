import pickle
import json
import sys
import os
import time
from datetime import timedelta

from asgiref.sync import async_to_sync
from django.db.models import Q
from django.utils import timezone
from rq import get_current_job
import django_rq
import django

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
    logger.info(f">> start working on task finalize_transaction {get_current_job().id}")
    sys.tracebacklimit = 1
    processed = False

    tx_, wallet_instance, connection = [pickle.loads(v) for v in args]
    tx_slate_id = str(tx_.tx_slate_id)

    # Initialize Wallet class from PythonSDK
    wallet = Wallet(
        wallet_dir=wallet_instance.wallet_dir,
        password=get_secret_value(wallet_instance.password_path))

    logger.info(">> Getting unprocessed slates from epic-box server..")
    encrypted_slates = wallet.get_tx_slates()

    logger.info(f">> Start decrypting {len(encrypted_slates)} slates")
    for encrypted_string in encrypted_slates:
        decrypted_slate = wallet.decrypt_tx_slates([encrypted_string])[0]
        slate_string, address = decrypted_slate
        db_tx, network_slate = json.loads(slate_string)
        decrypted_slate_id = json.loads(db_tx)[0]['tx_slate_id']

        # Confirm that requested transaction id is received
        print(decrypted_slate_id, tx_slate_id)
        if decrypted_slate_id in tx_slate_id:
            tx_.encrypted_slate = encrypted_string
            tx_.save()

            # Process slate
            logger.info(f">> Start processing {tx_}")
            processed = wallet.process_tx_slates([json.loads(slate_string)])

    if not processed:
        sys.tracebacklimit = 0
        wallet_instance.unlock()  # Release the wallet
        raise Exception('requested tx not found, re-try') from None

    tx_.status = 'finalized'
    tx_.save()

    # Post finalized transaction to the node (network)
    logger.info(f">>Sending {tx_} to network..")
    post_tx = wallet.post_transaction(tx_slate_id=str(tx_.tx_slate_id))

    if post_tx:
        tx_.status = 'finished'
        logger.info(f">> {tx_} finished successfully")
        # Update connection timestamps for time-lock function
        logger.info(f">> {update_connection_details(*connection)}")
    else:
        tx_.status = 'cancelled'
        logger.info(f">> {tx_} failed to post (cancelled)")

    tx_.archived = True
    tx_.save()
    wallet_instance.unlock()  # Release the wallet instance
    message = {"is_requested_tx": True}
    return utils.response(SUCCESS, str(message), message)


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


def check_wallet_transactions(*args):
    logger.info(f">> start working on task check_wallet_transactions {get_current_job().id}")
    wallet_instance = [pickle.loads(v) for v in args][0]

    # Initialize Wallet class from PythonSDK
    wallet = Wallet(
        wallet_dir=wallet_instance.wallet_dir,
        password=get_secret_value(wallet_instance.password_path))
    wallet_instance.lock()  # Lock the wallet instance

    decrypted_slates = 0

    logger.info(f">> [{wallet_instance.name}]: Getting unprocessed slates from epic-box server..")
    encrypted_slates = wallet.get_tx_slates()
    w_addr = wallet.epicbox.address

    logger.info(f">> [{wallet_instance.name}]: Getting slates from local database..")
    db_txs = wallet_instance.get_transactions()

    logger.info(f">> [{wallet_instance.name}]: Decrypting {len(encrypted_slates)} slates..")
    for encrypted_string in encrypted_slates:
        decrypted_slate = wallet.decrypt_tx_slates([encrypted_string])[0]
        slate_string, address = decrypted_slate
        db_tx, network_slate = json.loads(slate_string)
        decrypted_slate_id = json.loads(db_tx)[0]['tx_slate_id']

        tx_ = db_txs.filter(tx_slate_id=decrypted_slate_id).first()

        # If transaction is not in local db, delete it from epicbox
        if not tx_:
            logger.info(f">> {decrypted_slate_id} is archived or deleted from db, deleting from epicbox..")
            logger.info(wallet.post_delete_tx_slate(receiving_address=w_addr, slate=encrypted_string))
            logger.info(wallet.post_cancel_transaction(receiving_address=address, tx_slate_id=decrypted_slate_id))
            continue

        # If transaction is in local db match status
        match tx_.status:
            case 'initialized':
                if (timezone.now() - tx_.timestamp) > timedelta(minutes=5):
                    logger.info(f">> {tx_} old initialized tx, cleaning it up..")
                    logger.info(wallet.post_delete_tx_slate(receiving_address=w_addr, slate=encrypted_string))
                    logger.info(wallet.post_cancel_transaction(receiving_address=tx_.receiver_address,
                                                               tx_slate_id=decrypted_slate_id))
                    tx_.archived = True
                    tx_.status = 'cancelled'

            case 'finalized':
                logger.info(f">> {tx_} already finalized")
            case 'finished':
                logger.info(f">> {tx_} transaction finished")
                tx_.archived = True
            case 'cancelled':
                logger.info(f">> {tx_} already cancelled")
                tx_.archived = True

        logger.info(wallet.post_delete_tx_slate(receiving_address=w_addr, slate=encrypted_string))
        decrypted_slates += 1
        tx_.save()
        time.sleep(1)

    wallet_instance.unlock()  # Release the wallet instance

    # LOG WALLET'S TRANSACTION REPORT
    txs = wallet_instance.get_transactions()

    for tx in txs:
        print(tx)
        if tx.status == 'initialized':
            if (timezone.now() - tx.timestamp) > timedelta(minutes=5):
                logger.info(f">> {tx} old initialized tx, cleaning it up..")
                tx.archived = True
                tx.status = 'cancelled'
        tx.save()

    report = {
        "slates_received": len(encrypted_slates),
        "slates_decrypted": decrypted_slates,
        "unfinished_transactions": wallet_instance.get_transactions().filter(Q(status='initialized') | Q(status='finalized')).count()
        }

    print(report)
    return utils.response(SUCCESS, result=report)