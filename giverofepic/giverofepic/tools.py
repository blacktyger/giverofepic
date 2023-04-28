from Crypto.Cipher import AES
from hashlib import md5
import passpy
import base64
import json

from asgiref.sync import sync_to_async
from ninja_apikey.security import APIKeyAuth, check_apikey

from wallet.default_settings import API_KEY_HEADER, DEFAULT_SECRET_KEY
from wallet.epic_sdk.utils import logger


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


class CustomAPIKeyAuth(APIKeyAuth):
    """Custom API async auth"""
    param_name = API_KEY_HEADER

    @sync_to_async
    def authenticate(self, request, key):
        user = sync_to_async(check_apikey)(key)

        if not user:
            logger.warning("No auth for the request")
            return False

        request.user = user
        return user


class Encryption:
    """Manage encryption various elements in the project"""
    BLOCK_SIZE = AES.block_size

    def __init__(self, secret_key):
        self.secret_key = secret_key
        self.aes = self._get_aes()
        self.decrypted_data: str = ''
        self.encrypted_data: str = ''

    def _get_aes(self):
        m = md5()
        m.update(self.secret_key.encode('utf-8'))
        key = m.hexdigest()
        m = md5()
        m.update((self.secret_key + key).encode('utf-8'))
        iv = m.hexdigest()

        return AES.new(key.encode("utf8"), AES.MODE_CBC, iv.encode("utf8")[:self.BLOCK_SIZE])

    def _pad(self, byte_array):
        pad_len = self.BLOCK_SIZE - len(byte_array) % self.BLOCK_SIZE
        return byte_array + (bytes([pad_len]) * pad_len)

    @staticmethod
    def _unpad(byte_array):
        return byte_array[:-ord(byte_array[-1:])]

    def encrypt(self, raw_data: dict | str):
        if isinstance(raw_data, dict):
            raw_data = json.dumps(raw_data)
        try:
            data = self._pad(raw_data.encode("UTF-8"))
            self.encrypted_data = base64.urlsafe_b64encode(self.aes.encrypt(data)).decode('utf-8')
            return self.encrypted_data
        except Exception as e:
            logger.warning(f"encryption failed, {e}")

    def decrypt(self, encrypted_data: str):
        try:
            e_data = base64.urlsafe_b64decode(encrypted_data)
            self.decrypted_data = self._unpad(self.aes.decrypt(e_data)).decode('utf-8')
            payload = json.loads(self.decrypted_data)

            if isinstance(payload, dict):
                return payload

        except Exception as e:
            logger.warning(f"decryption failed, {e}")

        return None

class SecureRequest(Encryption):
    """Manage encrypted requests to secure data traffic with 3rd party apps"""

    def __init__(self, request):
        secret_key = request.headers.get(API_KEY_HEADER)
        if not secret_key:
            secret_key = DEFAULT_SECRET_KEY
        self.secret_key = secret_key

        super().__init__(secret_key)