import os
import pytest
from pathlib import Path

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.user import User, UserAuthenticationError
from lib.secure_variable import SecureVariable
from lib.db import DB
from lib.global_config import GlobalConfig
from lib.encryption import ENCRYPTED_VALUE_PREFIX, EncryptionConfigurationError, decrypt_data, encrypt_data
from tests import test_functions as Tests

TEST_CONFIG_FILE = os.path.normpath(f"{CURRENT_DIR}/../test-config.yml")
TEST_PUBLIC_KEY_FILE = os.path.normpath(f"{CURRENT_DIR}/../data/encryption_public_key.pem")
TEST_PRIVATE_KEY_FILE = os.path.normpath(f"{CURRENT_DIR}/../data/encryption_private_key.pem")


def _restore_test_config():
    GlobalConfig().override_config(config_location=TEST_CONFIG_FILE)


def _override_security_config(tmp_path, security_config):
    test_config = Path(TEST_CONFIG_FILE).read_text(encoding='utf-8')
    security_start = test_config.index('security:\n')
    security_end = test_config.index('\nsmtp:', security_start)

    config_file = tmp_path.joinpath('config.yml')
    config_file.write_text(
        test_config[:security_start] + security_config.rstrip() + '\n' + test_config[security_end + 1:],
        encoding='utf-8',
    )
    GlobalConfig().override_config(config_location=config_file)


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

def test_non_openssh_key_fails():
    user = User(1)
    try:

        with pytest.raises(ValueError) as e:
            user.update_ssh_private_key('-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----')

        assert str(e.value) == 'The setting ssh_private_key must contain a valid private key block'

        user_dict = user.to_dict()
        assert '_ssh_private_key' not in user_dict
    finally:
        user.update_ssh_private_key('')

def test_user_to_dict_does_not_expose_ssh_private_key():
    user = User(1)
    try:

        user.update_ssh_private_key(Tests.OPENSSH_EXAMPLE_PRIVATE_KEY)

        user_dict = user.to_dict()
        assert '_ssh_private_key' not in user_dict
    finally:
        user.update_ssh_private_key('')

def test_user_can_clear_ssh_private_key():
    user = User(1)
    try:

        user.update_ssh_private_key(Tests.OPENSSH_EXAMPLE_PRIVATE_KEY)

        assert user.has_ssh_private_key() is True

        user.update_ssh_private_key('')

        assert user.has_ssh_private_key() is False
        assert user.get_ssh_private_key() is None
        assert user._User__encrypted_ssh_private_key is None
        assert user._User__decrypted_ssh_private_key is None
    finally:
        user.update_ssh_private_key('')

def test_user_dict_is_clean():
    user = User(1)
    try:

        user.update_ssh_private_key(Tests.OPENSSH_EXAMPLE_PRIVATE_KEY)

        assert user.has_ssh_private_key() is True
        assert isinstance(user.get_ssh_private_key(), SecureVariable)
        assert user.get_ssh_private_key().get_value() == f"{Tests.OPENSSH_EXAMPLE_PRIVATE_KEY}\n"
        assert "BEGIN OPENSSH PRIVATE KEY" not in f"{user}"
        assert ENCRYPTED_VALUE_PREFIX not in f"{user}"

    finally:
        user.update_ssh_private_key('')

def test_encrypt_and_decrypt_data():
    data = 'secret value'

    try:
        encrypted_data = encrypt_data(data)

        assert encrypted_data.startswith(ENCRYPTED_VALUE_PREFIX)
        assert encrypted_data != data
        assert decrypt_data(encrypted_data) == data
    finally:
        _restore_test_config()


def test_decrypt_data_fails_relative_key_paths_from_config_file(tmp_path):
    key_folder = tmp_path.joinpath('keys')
    key_folder.mkdir()
    key_folder.joinpath('public.pem').write_text(Path(TEST_PUBLIC_KEY_FILE).read_text(encoding='utf-8'), encoding='utf-8')
    key_folder.joinpath('private.pem').write_text(Path(TEST_PRIVATE_KEY_FILE).read_text(encoding='utf-8'), encoding='utf-8')

    try:
        _override_security_config(
            tmp_path,
            'security:\n'
            '  encryption_public_key_file: keys/public.pem\n'
            '  encryption_private_key_file: keys/private.pem\n',
        )
        with pytest.raises(EncryptionConfigurationError):
            encrypt_data('secret value')
        with pytest.raises(EncryptionConfigurationError):
            decrypt_data('secret value')

    finally:
        _restore_test_config()

def test_user_stores_ssh_private_key_encrypted():
    user = User(1)

    try:
        user.update_ssh_private_key(Tests.OPENSSH_EXAMPLE_PRIVATE_KEY)

        raw_value = DB().fetch_one('SELECT ssh_private_key FROM users WHERE id = %s', params=(1,))[0]

        assert raw_value.startswith(ENCRYPTED_VALUE_PREFIX)
        assert Tests.OPENSSH_EXAMPLE_PRIVATE_KEY not in raw_value
        ssh_private_key = User(1).get_ssh_private_key()
        assert isinstance(ssh_private_key, SecureVariable)
        assert ssh_private_key.get_value() == f"{Tests.OPENSSH_EXAMPLE_PRIVATE_KEY}\n"
    finally:
        User(1).update_ssh_private_key('')


def test_user_error_without_key(tmp_path):
    user = User(1)

    try:
        _override_security_config(tmp_path, 'security: {}\n')

        with pytest.raises(ValueError):
            user.update_ssh_private_key(Tests.OPENSSH_EXAMPLE_PRIVATE_KEY)

        assert user.has_ssh_private_key() is False
        assert user._User__encrypted_ssh_private_key is None
        assert user._User__decrypted_ssh_private_key is None
    finally:
        _restore_test_config()

EXAMPLE_DOCKER_CREDENTIALS = [
    {'registry': 'ghcr.io', 'username': 'myuser', 'password': 'mypassword'},
    {'registry': 'docker.io', 'username': 'anotheruser', 'password': 'anotherpassword'},
]

def test_user_dict_does_not_expose_docker_credentials():
    user = User(1)
    try:
        user.update_docker_credentials(EXAMPLE_DOCKER_CREDENTIALS)

        user_dict = user.to_dict()
        assert '_docker_credentials' not in user_dict
        assert '_has_docker_credentials' in user_dict
        assert user_dict['_has_docker_credentials'] is True
        assert 'mypassword' not in str(user_dict)
        assert ENCRYPTED_VALUE_PREFIX not in str(user_dict)
    finally:
        user.update_docker_credentials(None)

def test_user_can_clear_docker_credentials():
    user = User(1)
    try:
        user.update_docker_credentials(EXAMPLE_DOCKER_CREDENTIALS)
        assert user.has_docker_credentials() is True

        user.update_docker_credentials(None)

        assert user.has_docker_credentials() is False
        assert user.get_docker_credentials() is None
        assert user._User__encrypted_docker_credentials is None
        assert user._User__decrypted_docker_credentials is None
    finally:
        user.update_docker_credentials(None)

def test_user_can_clear_docker_credentials_with_empty_list():
    user = User(1)
    try:
        user.update_docker_credentials(EXAMPLE_DOCKER_CREDENTIALS)
        assert user.has_docker_credentials() is True

        user.update_docker_credentials([])

        assert user.has_docker_credentials() is False
        assert user.get_docker_credentials() is None
    finally:
        user.update_docker_credentials(None)

def test_user_stores_docker_credentials_encrypted():
    user = User(1)
    try:
        user.update_docker_credentials(EXAMPLE_DOCKER_CREDENTIALS)

        raw_value = DB().fetch_one('SELECT docker_credentials FROM users WHERE id = %s', params=(1,))[0]

        assert raw_value.startswith(ENCRYPTED_VALUE_PREFIX)
        assert 'mypassword' not in raw_value

        creds = User(1).get_docker_credentials()
        assert isinstance(creds, list)
        assert len(creds) == 2
        assert creds[0]['registry'] == 'ghcr.io'
        assert creds[0]['username'] == 'myuser'
        assert isinstance(creds[0]['password'], SecureVariable)
        assert creds[0]['password'].get_value() == 'mypassword'
    finally:
        User(1).update_docker_credentials(None)

def test_user_docker_credentials_repr_does_not_leak_password():
    user = User(1)
    try:
        user.update_docker_credentials(EXAMPLE_DOCKER_CREDENTIALS)
        assert 'mypassword' not in f"{user}"
        assert ENCRYPTED_VALUE_PREFIX not in f"{user}"
    finally:
        user.update_docker_credentials(None)

def test_invalid_docker_credentials_not_a_list():
    user = User(1)
    with pytest.raises(ValueError, match='must be a list'):
        user.update_docker_credentials('not-a-list')

def test_invalid_docker_credentials_missing_fields():
    user = User(1)
    with pytest.raises(ValueError, match="non-empty 'password'"):
        user.update_docker_credentials([{'registry': 'ghcr.io', 'username': 'user'}])

def test_invalid_docker_credentials_empty_registry():
    user = User(1)
    with pytest.raises(ValueError, match="non-empty 'registry'"):
        user.update_docker_credentials([{'registry': '  ', 'username': 'user', 'password': 'pass'}])

def test_docker_credentials_error_without_encryption_key(tmp_path):
    user = User(1)
    try:
        _override_security_config(tmp_path, 'security: {}\n')

        with pytest.raises(ValueError, match='encryption is not configured'):
            user.update_docker_credentials(EXAMPLE_DOCKER_CREDENTIALS)

        assert user.has_docker_credentials() is False
        assert user._User__encrypted_docker_credentials is None
        assert user._User__decrypted_docker_credentials is None
    finally:
        _restore_test_config()

def test_user_can_use_orchestrator():
    user = User(1)
    assert user.can_use_orchestrator('docker') is True
    # the DEFAULT user for local usage has host execution (container: null in usage scenario flows) enabled out of the box
    assert user.can_use_orchestrator('host') is True

    # every other user does not have host execution unless explicitly granted
    Tests.insert_user(763, 'no-host-orchestrator-user')
    DB().query("UPDATE users SET capabilities = capabilities #- '{measurement,orchestrators,host}' WHERE id = 763")
    assert User(763).can_use_orchestrator('host') is False
