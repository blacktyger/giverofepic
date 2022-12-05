from epicpy import Wallet, Node

wallet = Wallet(secret=r'C:\Users\blacktyger\.epic\main\.owner_api_secret')
wallet.open_wallet(password='majkut11')

args = {
    "src_acct_name": None,
    "amount": int(float(0.1) * 10 ** 8),
    "minimum_confirmations": 1,
    "max_outputs": 1,
    "num_change_outputs": 5,
    "selection_strategy_is_use_all": False,
    "message": "",
    "target_slate_version": None,
    "payment_proof_recipient_address": None,
    "ttl_blocks": None,
    "send_args": None
    }

print(wallet.init_send_tx(args))