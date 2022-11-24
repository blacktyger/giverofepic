import json

from ninja import NinjaAPI

from wallet.epic_sdk import Wallet
from wallet.schema import TransactionIn, SlateIn

api = NinjaAPI()


@api.get("/wallet_balance/")
def add(request):
    dir = r"C:\Users\blacktyger\.epic\main\linux_wallet"
    password = "majkut11"
    wallet = Wallet(wallet_dir=dir, password=password)
    wallet.open()
    balance = wallet.retrieve_summary_info()
    wallet.close()
    return balance


@api.get("/get_slates")
def get_slates(request):
    dir = r"C:\Users\blacktyger\.epic\main\test_wallet"
    password = "majkut11"
    # addr = "esZ7pubuHN4Dyn8WsCRjzhe12ZtgHqmnthGoopA1iSskm2xwXcKK"

    """# 1 Initialize sender wallet """
    sender_wallet = Wallet(wallet_dir=dir, password=password)

    """# 2 RECEIVE SLATE AND SEND RESPONSE"""
    slates = sender_wallet.get_tx_slates()

    for slate_string in slates:
        slate_string, address = slate_string
        db_tx, network_slate = json.loads(slate_string)
        print(address)
        print(json.loads(db_tx)[0])
        print(json.loads(network_slate))
        print('\n\n')

    return {'success'}

@api.post("send_transaction")
def send_tx(request, tx: TransactionIn):
    dir = r"C:\Users\blacktyger\.epic\main\test_wallet"
    password = "majkut11"
    # addr = "esZ7pubuHN4Dyn8WsCRjzhe12ZtgHqmnthGoopA1iSskm2xwXcKK"

    """# 1 Initialize sender wallet """
    sender_wallet = Wallet(wallet_dir=dir, password=password)

    """# 2 CREATE AND POST TX SLATE"""
    new_tx = sender_wallet.create_tx_slate(amount=tx.amount)
    print(new_tx)

    post_new_tx_slate = sender_wallet.post_tx_slate(tx.address, new_tx)
    print(post_new_tx_slate)

    return post_new_tx_slate

