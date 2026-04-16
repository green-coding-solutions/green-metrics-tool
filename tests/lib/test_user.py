import os
import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.user import User, UserAuthenticationError
from lib.secure_variable import SecureVariable
from lib.db import DB
from lib.encryption import ENCRYPTED_VALUE_PREFIX, decrypt_data, encrypt_data
from tests import test_functions as Tests


def test_user_zero_fails():
    with pytest.raises(UserAuthenticationError) as e:
        User(0)
    assert str(e.value) == 'User 0 is system user and cannot log in'

def test_empty_token_fails():
    with pytest.raises(UserAuthenticationError) as e:
        User.authenticate(SecureVariable(''))
    assert str(e.value) == 'User with corresponding token not found'

def test_even_if_token_set_for_user_zero_authenticate_still_fails():
    Tests.update_user_token(0, 'asd')

    with pytest.raises(UserAuthenticationError) as e:
        User.authenticate(SecureVariable('asd'))
    assert str(e.value) == 'User 0 is system user and cannot log in'

def test_user_to_dict_does_not_expose_ssh_private_key():
    user = User(1)
    try:
        user.update_ssh_private_key('-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----')

        user_dict = user.to_dict()
        assert '_ssh_private_key' not in user_dict
    finally:
        user.update_ssh_private_key('')

def test_user_can_clear_ssh_private_key():
    user = User(1)
    try:
        user.update_ssh_private_key('-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----')

        user.update_ssh_private_key('')

        assert user.has_ssh_private_key() is False
        assert user.get_ssh_private_key() is None
    finally:
        user.update_ssh_private_key('')

def test_encrypt_and_decrypt_data():
    data = 'secret value'

    encrypted_data = encrypt_data(data)

    assert encrypted_data.startswith(ENCRYPTED_VALUE_PREFIX)
    assert encrypted_data != data
    assert decrypt_data(encrypted_data) == data

def test_user_stores_ssh_private_key_encrypted():
    user = User(1)
    private_key = '-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----'

    try:
        user.update_ssh_private_key(private_key)

        raw_value = DB().fetch_one('SELECT ssh_private_key FROM users WHERE id = %s', params=(1,))[0]

        assert raw_value.startswith(ENCRYPTED_VALUE_PREFIX)
        assert private_key not in raw_value
        assert User(1).get_ssh_private_key() == f'{private_key}\n'
    finally:
        User(1).update_ssh_private_key('')
