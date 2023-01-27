"""Utils for `wallet` app"""

import passpy

storage = passpy.store.Store()


def get_secret_value(path: str):
    """Return value stored with `passpy`"""
    return storage.get_key(path=path).strip()