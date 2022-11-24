import datetime
import decimal
import json

from ninja import NinjaAPI, Schema

from wallet.epic_sdk import Wallet
from wallet.models import Transaction
from wallet.schema import TransactionSchema, CancelTransaction

api = NinjaAPI()

"""#  Initialize Server Wallet wallet """
directory = r"C:\Users\blacktyger\.epic\main"
password = "majkut11"
wallet = Wallet(wallet_dir=directory, password=password)


@api.get("/get_wallet")
def get_wallet(request):
    wallet.open()
    balance = wallet.retrieve_summary_info()
    wallet.close()
    return balance


@api.get("/get_transactions")
def get_transactions(request):
    return wallet.get_transactions()


@api.get("/get_slates")
def get_slates(request):
    """# 2 RECEIVE SLATE AND SEND RESPONSE"""
    slates = wallet.get_tx_slates()

    for slate_string in slates:
        slate_string, address = slate_string
        db_tx, network_slate = json.loads(slate_string)
        print(address)
        print(json.loads(db_tx)[0])
        print(json.loads(network_slate))
        print('\n\n')

    return slates


@api.post("/cancel_transaction")
def cancel_transaction(request, cancel: CancelTransaction):
    cancel_epicbox = wallet.post_cancel_transaction(**cancel.dict())
    cancel_database = wallet.cancel_tx(tx_slate_id=cancel.tx_slate_id)
    return [cancel_epicbox, cancel_database]


@api.post("send_transaction")
def send_tx(request, tx: TransactionSchema):
    """# CREATE AND POST TX SLATE"""
    init_tx_slate = wallet.create_tx_slate(amount=tx.amount)

    try:
        tx_args = Transaction.parse_init_slate(init_tx_slate)
        tx_args['receiver_address'] = tx.receiver_address
        tx_args['sender_address'] = wallet.epicbox.address
        tx_args['amount'] = tx.amount
        tx_args['status'] = "initialized"
        tx_args['slates']['init_slate'] = init_tx_slate

        transaction = Transaction.objects.create(**tx_args)
        wallet.post_tx_slate(tx.address, init_tx_slate)

        return transaction
    except:
        print(wallet.cancel_tx_slate(slate=init_tx_slate))


