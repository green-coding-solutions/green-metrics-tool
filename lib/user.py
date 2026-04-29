import json
import hashlib

from lib.secure_variable import SecureVariable
from lib.db import DB
from lib.encryption import EncryptionConfigurationError, decrypt_data, encrypt_data, is_valid_openssh_private_key

def get_nested_value(dictionary, path):
    keys = path.split('.', 1)
    key = keys[0]
    if len(keys) == 1:
        return (dictionary, key, dictionary[key])
    return get_nested_value(dictionary[key], keys[1])

class User():

    def __init__(self, user_id: int):
        if user_id == 0:
            raise UserAuthenticationError('User 0 is system user and cannot log in')

        user = DB().fetch_one("""
                SELECT id, name, capabilities, ssh_private_key
                FROM users
                WHERE id = %s
                """, params=(user_id, ))
        if not user:
            raise UserAuthenticationError(f"User with id {user_id} not found in database")

        self._id = user[0]
        self._name = user[1]
        self._capabilities = user[2]
        self.__encrypted_ssh_private_key = user[3]
        # value is not populated here directly as due to the security setup of GMT
        # the server sometimes only has the public key to encrypt and would fail if the
        # private key is missing
        self.__decrypted_ssh_private_key = None

    def to_dict(self):
        values = self.__dict__.copy()
        del values['_id']
        values.pop('_User__encrypted_ssh_private_key', None)
        values.pop('_User__decrypted_ssh_private_key', None)
        values['_has_ssh_private_key'] = bool(self.__encrypted_ssh_private_key)
        return values

    def __repr__(self):
        return str(self.to_dict())

    def update(self):
        DB().query("""
            UPDATE users
            SET capabilities = %s
            WHERE id = %s
            """, params=(json.dumps(self._capabilities), self._id, ))


    def _save_key_to_db(self, encrypted_value):
        DB().query("""
            UPDATE users
            SET ssh_private_key = %s
            WHERE id = %s
            """, params=(encrypted_value, self._id, ))

    def visible_users(self):
        return self._capabilities['user']['visible_users']

    def is_super_user(self):
        return bool(self._capabilities['user']['is_super_user'])

    def can_use_machine(self, machine_id: int):
        return machine_id in self._capabilities['machines']

    def can_use_route(self, route: str):
        return route in self._capabilities['api']['routes']

    def can_schedule_job(self, schedule_mode: str):
        return schedule_mode in self._capabilities['jobs']['schedule_modes']

    def change_setting(self, name, value):
        if not self.can_change_setting(name):
            raise ValueError(f"You cannot change this setting: {name}")

        match name:
            case 'measurement.skip_optimizations' | 'measurement.dev_no_sleeps' | 'measurement.phase_padding' | 'measurement.skip_volume_inspect':
                if not isinstance(value, bool):
                    raise ValueError(f'The setting {name} must be boolean')
            case 'measurement.flow_process_duration' | 'measurement.total_duration':
                if not (isinstance(value, int) or value.isdigit()) or int(value) <= 0 or int(value) > 86400:
                    raise ValueError(f'The setting {name} must be between 1 and 86400')
                value = int(value)
            case 'measurement.disabled_metric_providers':
                value = set(value)
                allowed_values = {'network_connections_tcpdump_system', 'network_connections_proxy_container'} # set
                if not value.issubset(allowed_values):
                    raise ValueError(f'The setting {name} must be in {allowed_values} but is {value}')
                value = list(value) # transform back, as it is not json serializable. But we need the unique transform of set beforehand
            case 'measurement.system_check_threshold':
                if not (isinstance(value, int) or value.isdigit()) or int(value) not in [1, 2, 3]:
                    raise ValueError(f'The setting {name} must be 1, 2 or 3')
                value = int(value)
            case 'measurement.pre_test_sleep' | 'measurement.idle_duration' | 'measurement.baseline_duration' | 'measurement.post_test_sleep' | 'measurement.phase_transition_time' | 'measurement.wait_time_dependencies':
                if not (isinstance(value, int) or value.isdigit()) or int(value) <= 0 or int(value) > 86400:
                    raise ValueError(f'The setting {name} must be between 1 and 86400')
                value = int(value)
            case 'ssh_private_key':
                self.update_ssh_private_key(value)
                return
            case _:
                raise ValueError(f'The setting {name} is unknown')

        (element, last_key, _) = get_nested_value(self._capabilities, name)
        element[last_key] = value
        self.update()

    def has_ssh_private_key(self):
        return bool(self.__encrypted_ssh_private_key)

    def get_ssh_private_key(self):
        if self.__decrypted_ssh_private_key is None and self.has_ssh_private_key():
            decrypted_ssh_private_key = decrypt_data(self.__encrypted_ssh_private_key)
            self.__decrypted_ssh_private_key = SecureVariable(decrypted_ssh_private_key) if decrypted_ssh_private_key else None

        if self.__decrypted_ssh_private_key is None:
            return None
        return self.__decrypted_ssh_private_key.get_value()



    def update_ssh_private_key(self, key):

        if key is None:
            self._save_key_to_db(None)
            self.__encrypted_ssh_private_key = self.__decrypted_ssh_private_key = None
            return

        if not isinstance(key, str):
            raise ValueError('The setting ssh_private_key must be a string')

        normalized_value = key.strip()

        if normalized_value == '':
            self._save_key_to_db(None)
            self.__encrypted_ssh_private_key = self.__decrypted_ssh_private_key = None
            return

        if not is_valid_openssh_private_key(normalized_value):
            raise ValueError('The setting ssh_private_key must contain a valid private key block')

        normalized_value = f"{normalized_value.strip()}\n" # normalize line ends

        try:
            encrypted_value = encrypt_data(normalized_value)
        except EncryptionConfigurationError as e:
            raise ValueError('Cannot store SSH key: encryption is not configured on this server') from e

        self._save_key_to_db(encrypted_value)
        self.__encrypted_ssh_private_key = encrypted_value
        self.__decrypted_ssh_private_key = SecureVariable(normalized_value) if normalized_value else None

    def can_change_setting(self, name):
        return name in self._capabilities['user']['updateable_settings']

    def has_api_quota(self, route: str):
        if route in self._capabilities['api']['quotas']:
            return self._capabilities['api']['quotas'][route] > 0
        return True # None means infinite amounts

    def deduct_api_quota(self, route: str, amount: int):
        if route in self._capabilities['api']['quotas']:
            self._capabilities['api']['quotas'][route] -= amount
            self.update()

    def has_measurement_quota(self, machine_id: int):
        machine_id = str(machine_id) # json does not support integer keys
        if machine_id in self._capabilities['measurement']['quotas']:
            return self._capabilities['measurement']['quotas'][machine_id] > 0
        return True # None means infinite amounts

    def deduct_measurement_quota(self, machine_id: int, amount: int):
        machine_id = str(machine_id)  # json does not support integer keys
        if machine_id in self._capabilities['measurement']['quotas']:
            self._capabilities['measurement']['quotas'][machine_id] -= amount
            self.update()

    @classmethod
    def authenticate(cls, token: SecureVariable | None):
        sha256_hash = hashlib.sha256()
        sha256_hash.update(token.get_value().encode('UTF-8'))

        user = DB().fetch_one("""
                SELECT id, name
                FROM users
                WHERE token = %s
                """, params=((sha256_hash.hexdigest()), ))
        if not user:
            raise UserAuthenticationError('User with corresponding token not found') # do never output token everywhere cause it might land in logs

        return cls(user[0])

class UserAuthenticationError(Exception):
    pass


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('token', help='Please supply a token to get the user')

    args = parser.parse_args()  # script will exit if arguments not present

    authenticated_user_id = User.authenticate(SecureVariable(args.token))
    print("User is", User(authenticated_user_id))
