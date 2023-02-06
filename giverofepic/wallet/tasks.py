from datetime import timedelta
import pickle
import json
import os

from django.utils import timezone
from django.db.models import Q
from rq import get_current_job
import django_rq
import django

# Must be called before imports from Django components

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "giverofepic.settings")
django.setup()

from .default_settings import SUCCESS, ERROR, MINIMUM_CONFIRMATIONS, DELETE_AFTER_MINUTES
from .epic_sdk import Wallet, utils
from faucet.models import Client
from .models import Transaction
from .logger_ import get_logger
from . import get_secret_value


"""Initialize Logger"""
logger = get_logger()


"""Initialize Queue for managing task"""
redis_conn = django_rq.get_connection('default')


def send_new_transaction(*args):
    this_task = get_current_job()
    logger.info(f">> start working on task send_new_transaction {this_task.id}")

    amount, address, wallet_instance, client = [pickle.loads(v) for v in args]
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
    init_tx_slate = wallet.create_tx_slate(amount=amount, min_confirmations=MINIMUM_CONFIRMATIONS)

    try:
        ## >> Parse tx_args and prepare transaction slate
        tx_args = Transaction.parse_init_slate(init_tx_slate)
        tx_args['sender'] = wallet_instance
        tx_args['receiver'] = client.receiver
        tx_args['initial_slate'] = init_tx_slate
        tx_args['status'] = "initialized"
        tx_args['amount'] = amount

        ## >> Create new Transaction object
        transaction = Transaction.objects.create(**tx_args)
        response_ = wallet.post_tx_slate(address, init_tx_slate)

        if response_:
            wallet_instance.last_transaction = transaction
            wallet_instance.save()
            client.update_activity(status=transaction.status)
            response = utils.response(SUCCESS, 'post tx success', {'tx_slate_id': transaction.tx_slate_id})
            logger.info(response)
        else:
            client.update_activity(status="transaction failed (initialize stage)")
            transaction.remove_client_data()
            response = utils.response(ERROR, f'post tx failed')
            logger.error(response)

    except Exception as e:
        wallet.cancel_tx_slate(slate=init_tx_slate)
        client.update_activity(status="transaction failed (initialize stage)")
        response = utils.response(ERROR, f"post tx failed and canceled, {str(e)}")
        logger.error(response)

    wallet_instance.unlock()  # Release wallet
    return response


def finalize_transactions(*args):
    logger.info(f">> start working on task finalize_transactions {get_current_job().id}")
    to_finalize = []
    to_process = []
    to_post = []

    # Unpickle args
    pending_transactions = [pickle.loads(v) for v in args][0]
    pending_transactions_ids = [str(tx.tx_slate_id) for tx in pending_transactions]

    # Initialize Wallet class from PythonSDK and Client
    wallet_instance = pending_transactions[0].sender
    client = Client.from_receiver(pending_transactions[0].receiver)

    wallet = Wallet(
        wallet_dir=wallet_instance.wallet_dir,
        password=get_secret_value(wallet_instance.password_path))

    logger.info(f">> Getting unprocessed slates for '{wallet_instance.name}' from epic-box server..")
    encrypted_slates = wallet.get_tx_slates()

    # Finish if there is no new slates available
    if len(encrypted_slates) < 1:
        logger.warning('No new encrypted_slates available on the epicbox server')
        return

    logger.info(f">> Start decrypting {len(encrypted_slates)} slates")
    for encrypted_string in encrypted_slates:
        decrypted_slate = wallet.decrypt_tx_slates([encrypted_string])[0]
        slate_string, address = decrypted_slate
        db_tx, network_slate = json.loads(slate_string)
        decrypted_slate_id = json.loads(db_tx)[0]['tx_slate_id']

        # Match decrypted slate id with pending transaction in local db
        if decrypted_slate_id in pending_transactions_ids:
            # Get and update transaction object
            tx_ = pending_transactions.get(tx_slate_id=decrypted_slate_id)
            tx_.encrypted_slate = encrypted_string
            tx_.save()

            # Update local queryset (remove processed slate)
            pending_transactions = pending_transactions.exclude(tx_slate_id=decrypted_slate_id)

            # Append to further processing
            to_finalize.append(tx_)
            to_process.append(json.loads(slate_string))

    if not to_process:
        logger.warning('Decrypted slates from epicbox server are not present in the local database')
        return

    if len(pending_transactions) > 0:
        logger.warning(f'{len(pending_transactions)} Pending local transactions are not in the epicbox server')

    # Process the matching encrypted slates in the wallet instance
    logger.info(f">> Start processing {len(to_process)} slates..")
    wallet.process_tx_slates(to_process)

    # Update transactions object and append to posting list
    for tx_ in to_finalize:
        tx_.status = 'finalized'
        tx_.save()
        to_post.append(tx_)

    # Post finalized transaction slate to the node (network)
    for transaction in to_post:
        logger.info(f">> Sending {transaction} to the network..")
        post_tx = wallet.post_transaction(tx_slate_id=str(transaction.tx_slate_id))

        if post_tx:
            transaction.status = 'finished'
            logger.info(f">> {transaction} finished successfully")
            # TODO:  Update connection timestamps for time-lock function
        else:
            transaction.status = 'cancelled'
            logger.info(f">> {transaction} failed to post (cancelled)")

        logger.info(f">> {client.update_activity(status=transaction.status)}")
        transaction.remove_client_data()
        transaction.archived = True
        transaction.save()

    wallet_instance.unlock()  # Release the wallet instance
    print(f"======================"
          f"\n=== UPDATE  REPORT ==="
          f"\npending_transactions: {len(pending_transactions)}"
          f"\nencrypted_slates: {len(encrypted_slates)}"
          f"\nto_process: {len(to_process)}"
          f"\nto_finalize: {len(to_finalize)}"
          f"\nto_post: {len(to_post)}"
          f"\n======================")

def cancel_transaction(tx):
    logger.info(f">> start working on task cancel_transaction {get_current_job().id}")
    transaction = pickle.loads(tx)
    wallet_instance = transaction.sender
    tx_slate_id = str(transaction.tx_slate_id)

    # Initialize Wallet class from PythonSDK and Client
    client = Client.from_receiver(transaction.receiver)
    wallet = Wallet(
        wallet_dir=wallet_instance.wallet_dir,
        password=get_secret_value(wallet_instance.password_path))
    wallet_instance.lock()  # Lock the wallet instance

    # Cancel in local wallet history
    logger.info(f"Local wallet transaction: {wallet.cancel_tx_slate(tx_slate_id=tx_slate_id)}")
    wallet.post_delete_tx_slate(receiving_address=transaction.sender.address, slate=transaction.encrypted_slate)

    # Cancel in epic-box server
    cancel = wallet.post_cancel_transaction(
        receiving_address=transaction.receiver.address,
        tx_slate_id=tx_slate_id)
    logger.info(f"Epicbox slate canceled: {cancel['status'] if 'status' in cancel else 'failed'}")

    wallet_instance.unlock()  # Release wallet
    transaction.archived = True
    transaction.status = 'cancelled'
    transaction.save()

    # Update receiver lock status in database
    client.update_activity(status=transaction.status)
    transaction.remove_client_data()
    return utils.response(SUCCESS, 'transaction canceled')


def rescan_and_clean_transactions(wallet):
    logger.info(f">> start working on task check_wallet_transactions {get_current_job().id}")
    wallet_instance = pickle.loads(wallet)
    decrypted_slates = 0

    # Initialize Wallet class from PythonSDK
    wallet = Wallet(
        wallet_dir=wallet_instance.wallet_dir,
        password=get_secret_value(wallet_instance.password_path))
    wallet_instance.lock()  # Lock the wallet instance

    logger.info(f">> [{wallet_instance.name}]: Getting unprocessed slates from epic-box server..")
    encrypted_slates = wallet.get_tx_slates()
    w_addr = wallet.epicbox.address

    logger.info(f">> [{wallet_instance.name}]: Getting slates from local database..")
    pending_db_txs = wallet_instance.get_pending_transactions()

    logger.info(f">> [{wallet_instance.name}]: Decrypting {len(encrypted_slates)} slates..")
    for encrypted_string in encrypted_slates:
        decrypted_slate = wallet.decrypt_tx_slates([encrypted_string])[0]
        slate_string, address = decrypted_slate
        db_tx, network_slate = json.loads(slate_string)
        decrypted_slate_id = json.loads(db_tx)[0]['tx_slate_id']
        tx_ = pending_db_txs.filter(tx_slate_id=decrypted_slate_id).first()

        # If transaction is not in local db, delete it from epicbox
        if not tx_:
            logger.info(f">> {decrypted_slate_id} is archived or deleted from db, deleting from epicbox..")
            logger.info(wallet.post_delete_tx_slate(receiving_address=w_addr, slate=encrypted_string))
            logger.info(wallet.post_cancel_transaction(receiving_address=address, tx_slate_id=decrypted_slate_id))
            continue

        # If transaction is in local db match status
        match tx_.status:
            case 'initialized':
                if (timezone.now() - tx_.timestamp) > timedelta(minutes=DELETE_AFTER_MINUTES):
                    logger.info(f">> {tx_} old initialized tx, cleaning it up..")
                    logger.info(wallet.post_delete_tx_slate(receiving_address=w_addr, slate=encrypted_string))
                    logger.info(wallet.post_cancel_transaction(receiving_address=tx_.receiver.address,
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
        tx_.remove_client_data()

    wallet_instance.unlock()  # Release the wallet instance

    # LOG WALLET'S TRANSACTION REPORT
    report = {
        "slates_received": len(encrypted_slates),
        "slates_decrypted": decrypted_slates,
        "unfinished_transactions": wallet_instance.get_pending_transactions().filter(Q(status='initialized') | Q(status='finalized')).count()
        }

    logger.info(report)
    return utils.response(SUCCESS, result=report)