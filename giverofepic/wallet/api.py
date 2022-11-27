import json
import os

from ninja import NinjaAPI
from django.db.models import Q

from .const_values import *
from .epic_sdk import Wallet, utils
from .models import Transaction, WalletState, get_wallet_status, connection_details, connection_authorized
from .schema import TransactionSchema, CancelTransaction

api = NinjaAPI()


"""
Initialize Server Wallet - Epic-Box Sender I, 
- executing outgoing transactions.
"""
directory = r"C:\Users\blacktyger\.epic\main"
password = "majkut11"
NAME = "epic_box_1"

wallet = Wallet(wallet_dir=directory, password=password)
wallet.state, _ = WalletState.objects.get_or_create(name=NAME)
print(wallet.state.is_locked)


@api.post("/send_transaction")
def send_tx(request, tx: TransactionSchema):
    # """ VALIDATE TX_ARGS BEFORE START """ #
    tx_args = Transaction.validate_tx_args(tx.amount, tx.receiver_address)
    if tx_args['error']: return tx_args

    # """ AUTHORIZE CONNECTION WITH TIME-LOCK FUNCTION """ #
    authorized = connection_authorized(request, tx)
    if authorized['error']: return authorized

    # """ GET OR WAIT FOR UNLOCKED INSTANCE """ #
    is_unlocked = get_wallet_status(wallet)
    if is_unlocked['error']: return is_unlocked

    # """ MAKE SURE WALLET BALANCE IS SUFFICIENT """ #
    if not wallet.is_balance_enough(tx.amount):
        return utils.response(ERROR, wallet.state.error_msg())

    # """ START CREATING NEW TRANSACTION """ #
    wallet.state.lock()  # Lock the wallet instance

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
            print(connection_details(request, tx, update=True))
            response = utils.response(SUCCESS, 'post tx success', transaction.tx_slate_id)
        else:
            response = utils.response(ERROR, f'post tx failed')

    except Exception as e:
        wallet.cancel_tx_slate(slate=init_tx_slate)
        response = utils.response(ERROR, f"post tx failed and canceled, {str(e)}")

    wallet.state.unlock()  # Release wallet
    return response


@api.get("/get_slates")
def get_slates(request):
    """RECEIVE SLATE AND SEND RESPONSE"""
    # """ GET OR WAIT FOR UNLOCKED INSTANCE """ #
    is_unlocked = get_wallet_status(wallet)
    if is_unlocked['error']: return is_unlocked
    wallet.state.lock()  # Lock the wallet instance

    # DEFINE FUNCTION VARIABLES
    to_process = []
    processed = []
    to_post = []
    posted = 0

    print(">> Getting unprocessed slates from epic-box server..")
    encrypted_slates = wallet.get_tx_slates()
    w_addr = wallet.epicbox.address

    print(">> Getting slates from local database..")
    txs = Transaction.objects.filter(
        Q(archived=False) and (Q(receiver_address=w_addr) | Q(sender_address=w_addr)))

    # LIST OF TX_IDs FROM WALLET INSTANCE DB
    txs_ids = [str(tx.tx_slate_id) for tx in txs]

    # Filter new slates and append to list
    print(f">> Start decrypting {len(encrypted_slates)} slates")
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
                print(f">> {tx_} ready to process")
                to_process.append(json.loads(slate_string))

            elif 'finalized' in tx_.status:
                print(f">> {tx_} already finalized")
                print(wallet.post_delete_tx_slate(receiving_address=w_addr, slate=encrypted_string))

            elif 'finished' in tx_.status:
                print(f">> {tx_} already finished")
                tx_.archived = True
                print(wallet.post_delete_tx_slate(receiving_address=w_addr, slate=encrypted_string))

                # wallet.post_cancel_transaction(receiving_address=w_addr, tx_slate_id=incoming_slate_tx_id)
                # wallet.post_delete_canceled_tx_slates(receiving_address=w_addr, tx_slate_id=incoming_slate_tx_id)

            tx_.save()
        # Iterate through slates not known to this wallet instance,
        # most likely TxReceived type of slate, this wallet as receiver
        else:
            pass
            # print(wallet.post_delete_tx_slate(receiving_address=w_addr, slate=encrypted_string))

    # Process filtered slates
    print(f">> Start processing {len(to_process)} slates..")
    processed += wallet.process_tx_slates(to_process)

    if not processed:
        wallet.state.unlock()  # Release the wallet
        return utils.response(ERROR, "No slates processed")

    for tx_ in Transaction.objects.filter(status='initialized', archived=False):
        tx_.status = 'finalized'
        tx_.save()
        to_post.append(tx_)

    # Post finalized transactions to the node (network)
    print(f">> Start sending {len(to_post)} transactions..")
    for ready_tx in to_post:
        print(f">> sending {ready_tx}...")
        post_tx = wallet.post_transaction(tx_slate_id=str(ready_tx.tx_slate_id))
        print(post_tx)

        if post_tx:
            ready_tx.status = 'finished'
            ready_tx.archived = True
            ready_tx.save()
            print(f">> {ready_tx} posted, finished and archived successfully")
            posted += 1
        else:
            print(f">> {ready_tx} failed to post, ")

    report = {
        "slates_received": len(encrypted_slates),
        "slates_decrypted": len(to_process),
        "slates_processed": len(to_post),
        "txs_finished": posted
        }

    wallet.state.unlock()  # Release the wallet instance

    return utils.response(SUCCESS, 'success', report)


@api.get("/get_transactions")
def get_transactions(request):
    return wallet.get_transactions()


@api.post("/cancel_transaction")
def cancel_transaction(request, cancel: CancelTransaction):
    cancel_epicbox = wallet.post_cancel_transaction(**cancel.dict())
    cancel_database = wallet.cancel_tx(tx_slate_id=cancel.tx_slate_id)
    return [cancel_epicbox, cancel_database]


@api.post("/process_slates")
def process_slates(request, slates: str):
    slates = wallet.get_tx_slates()
    print(f"Processing {len(slates)} received slates")
    return wallet.process_tx_slates(slates)


@api.post("/finalize_transaction")
def finalize_transactions(request, slates: str):
    print(os.getcwd())
    with open('a.json', 'r') as f:
        slates = f.read()

    for tx in json.loads(json.loads(slates)):
        wallet.post_transaction(tx)
