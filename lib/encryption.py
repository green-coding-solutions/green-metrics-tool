import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken

from lib.global_config import GlobalConfig

ENCRYPTED_VALUE_PREFIX = 'gmt-encrypted:v1:'


class EncryptionConfigurationError(Exception):
    pass


def _get_configured_encryption_key():
    encryption_key = GlobalConfig().config.get('security', {}).get('encryption_key')

    if not isinstance(encryption_key, str) or encryption_key.strip() in ('', 'PLEASE_CHANGE_THIS_ENCRYPTION_KEY'):
        raise EncryptionConfigurationError('security.encryption_key must be set in config.yml before encrypting data')

    encryption_key = encryption_key.strip()
    if len(encryption_key) < 32:
        raise EncryptionConfigurationError('security.encryption_key must be at least 32 characters long')

    return encryption_key


def _get_fernet(encryption_key=None):
    encryption_key = encryption_key or _get_configured_encryption_key()
    derived_key = base64.urlsafe_b64encode(hashlib.sha256(encryption_key.encode('utf-8')).digest())
    return Fernet(derived_key)


def encrypt_data(data, encryption_key=None):
    if data is None:
        return None
    if not isinstance(data, str):
        raise ValueError('Only string values can be encrypted')
    if data.startswith(ENCRYPTED_VALUE_PREFIX):
        return data

    encrypted_data = _get_fernet(encryption_key).encrypt(data.encode('utf-8')).decode('utf-8')
    return f'{ENCRYPTED_VALUE_PREFIX}{encrypted_data}'


def is_encrypted_data(data):
    return isinstance(data, str) and data.startswith(ENCRYPTED_VALUE_PREFIX)


def decrypt_data(data, encryption_key=None):
    if data is None:
        return None
    if not isinstance(data, str):
        raise ValueError('Only string values can be decrypted')
    if not is_encrypted_data(data):
        return data

    encrypted_data = data.removeprefix(ENCRYPTED_VALUE_PREFIX)

    try:
        return _get_fernet(encryption_key).decrypt(encrypted_data.encode('utf-8')).decode('utf-8')
    except InvalidToken as exc:
        raise EncryptionConfigurationError('Could not decrypt stored data. Check security.encryption_key in config.yml') from exc
