"""Utils for `wallet` app"""
import passpy

storage = passpy.store.Store(gpg_bin='/usr/bin/gpg')


def get_secret_value(path: str):
    """Return value stored with `passpy`"""
    return storage.get_key(path=path).strip()


def get_short(address, extra_short: bool = False):
    address = str(address)
    try:
        return f"{address[0:4]}..{address[-4:]}" if not extra_short else f"{address[0:4]}.."
    except Exception:
        return address

