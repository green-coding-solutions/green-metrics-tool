import os
import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.user import User, UserAuthenticationError
from lib.secure_variable import SecureVariable
from tests import test_functions as Tests


def test_user_zero_fails():
    with pytest.raises(RuntimeError) as e:
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
