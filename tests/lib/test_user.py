import os
import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.user import User, UserAuthenticationError
from lib.secure_variable import SecureVariable
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

        assert user_dict['_has_ssh_private_key'] is True
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
