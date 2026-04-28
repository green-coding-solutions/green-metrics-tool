import base64
import binascii
import json
import os
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

from lib.global_config import GlobalConfig

ENCRYPTED_VALUE_PREFIX = 'gmt-encrypted:v1:'
ENCRYPTION_ALGORITHM = 'RSA-OAEP-SHA256+A256GCM'

class EncryptionConfigurationError(Exception):
    pass

class EncryptionError(Exception):
    pass



def _base64_encode(data):
    return base64.urlsafe_b64encode(data).decode('ascii')


def _base64_decode(data):
    return base64.urlsafe_b64decode(data.encode('ascii'))


def _resolve_configured_key_file(key):
    configured_key_file = GlobalConfig().config.get('security', {}).get(key)

    if not isinstance(configured_key_file, str) or configured_key_file.strip() == '':
        return None

    config_path = Path(configured_key_file.strip()).resolve()\

    if not config_path.is_file():
        raise EncryptionConfigurationError(f'security.{key} does not point to a readable file: {config_path}')

    return config_path


def _load_public_key():
    public_key_file = _resolve_configured_key_file('encryption_public_key_file')

    if not public_key_file:
        return None

    try:
        public_key = serialization.load_pem_public_key(public_key_file.read_bytes())
    except ValueError as exc:
        raise EncryptionConfigurationError(
            f'Could not load public encryption key from {public_key_file}'
        ) from exc

    if not isinstance(public_key, rsa.RSAPublicKey):
        raise EncryptionConfigurationError('security.encryption_public_key_file must contain an RSA public key')

    return public_key


def _load_private_key():
    private_key_file =  _resolve_configured_key_file('encryption_private_key_file')

    if not private_key_file:
        return None

    try:
        private_key = serialization.load_pem_private_key(private_key_file.read_bytes(), password=None)
    except (TypeError, ValueError) as exc:
        raise EncryptionConfigurationError(
            f'Could not load private encryption key from {private_key_file}'
        ) from exc

    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise EncryptionConfigurationError('security.encryption_private_key_file must contain an RSA private key')

    return private_key

def is_valid_openssh_private_key(data: str) -> bool:
    if not data.startswith("-----BEGIN OPENSSH PRIVATE KEY-----"):
        return False
    if not data.strip().endswith("-----END OPENSSH PRIVATE KEY-----"):
        return False

    try:
        serialization.load_ssh_private_key(
            data.encode(),
            password=None,  # or b"passphrase" if encrypted
            backend=default_backend()
        )
        return True
    except Exception: # pylint: disable=broad-exception-caught
        return False

def encrypt_data(data):
    if data is None:
        return None

    if not isinstance(data, str):
        raise ValueError('Only string values can be encrypted')

    public_key = _load_public_key()
    if public_key is None:
        raise EncryptionConfigurationError('No public encryption key configured. Check security.encryption_public_key_file in config.yml')


    # We need to generate a key and then encrypt this key as RSA can not encypt a full ssh key.
    aes_key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    encrypted_data = AESGCM(aes_key).encrypt(nonce, data.encode('utf-8'), None)
    encrypted_key = public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )

    envelope = {
        'alg': ENCRYPTION_ALGORITHM,
        'encrypted_key': _base64_encode(encrypted_key),
        'nonce': _base64_encode(nonce),
        'ciphertext': _base64_encode(encrypted_data),
    }

    encrypted_payload = _base64_encode(
        json.dumps(envelope, separators=(',', ':'), sort_keys=True).encode('utf-8')
    )

    return f'{ENCRYPTED_VALUE_PREFIX}{encrypted_payload}'


def decrypt_data(data):

    if data is None:
        return None

    if not isinstance(data, str):
        raise ValueError('Only string values can be decrypted')

    private_key = _load_private_key()
    if private_key is None:
        raise EncryptionConfigurationError('No private encryption key configured. Check security.encryption_private_key_file in config.yml')


    if not data.startswith(ENCRYPTED_VALUE_PREFIX):
        raise EncryptionError('Data does not appear to be encrypted with the expected format')

    encrypted_payload = data.removeprefix(ENCRYPTED_VALUE_PREFIX)

    try:
        envelope = json.loads(_base64_decode(encrypted_payload).decode('utf-8'))
        if envelope.get('alg') != ENCRYPTION_ALGORITHM:
            raise ValueError(f"Unsupported encryption algorithm: {envelope.get('alg')}")

        aes_key = private_key.decrypt(
            _base64_decode(envelope['encrypted_key']),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        decrypted_data = AESGCM(aes_key).decrypt(
            _base64_decode(envelope['nonce']),
            _base64_decode(envelope['ciphertext']),
            None,
        )
        return decrypted_data.decode('utf-8')
    except (binascii.Error, InvalidTag, KeyError, TypeError, ValueError) as exc:
        raise EncryptionConfigurationError(
            'Could not decrypt stored data. Check security.encryption_private_key_file in config.yml'
        ) from exc
