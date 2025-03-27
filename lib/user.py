import json
import hashlib
import uuid

from lib.secure_variable import SecureVariable
from lib.db import DB

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
                SELECT id, name, capabilities
                FROM users
                WHERE id = %s
                """, params=(user_id, ))
        if not user:
            raise UserAuthenticationError(f"User with id {user_id} not found in database")

        self._id = user[0]
        self._name = user[1]
        self._capabilities = user[2]

    def to_dict(self):
        values = self.__dict__.copy()
        del values['_id']
        return values

    def __repr__(self):
        return str(self.to_dict())

    def update(self):
        DB().query("""
            UPDATE users
            SET capabilities = %s
            WHERE id = %s
            """, params=(json.dumps(self._capabilities), self._id, ))

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
            case 'measurement.settings.flow_process_duration' | 'measurement.settings.total_duration':
                if not (isinstance(value, int) or value.isdigit()) or int(value) <= 0 or int(value) > 86400:
                    raise ValueError(f'The setting {name} must be between 1 and 86400')
                value = int(value)
            case 'measurement.disabled_metric_providers':
                value = set(value)
                allowed_values = {'NetworkConnectionsTcpdumpSystemProvider', 'NetworkConnectionsProxyContainerProvider'} # set
                if not value.issubset(allowed_values):
                    raise ValueError(f'The setting {name} must be in {allowed_values} but is {value}')
                value = list(value) # transform back, as it is not json serializable. But we need the unique transform of set beforehand
            case _:
                raise ValueError(f'The setting {name} is unknown')

        (element, last_key, _) = get_nested_value(self._capabilities, name)
        element[last_key] = value
        self.update()

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
    def authenticate(cls, token: SecureVariable | None, silent=False):
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

    @staticmethod
    def get_new(name=None):

        token = str(uuid.uuid4()).upper()
        sha256_hash = hashlib.sha256()
        sha256_hash.update(token.encode('UTF-8'))

        default_capabilities = {
            "api": {
                "quotas": { # An empty dictionary here means that no quotas apply
                },
                "routes": [ # This will be dynamically loaded from the current main.py for all applicable routes
                    "/v1/carbondb/add",
                    "/v1/ci/measurement/add",
                    "/v1/software/add",
                    "/v1/hog/add",
                    "/v1/authentication/data",
                ]
            },
            "jobs": {
                "schedule_modes": [
                    "one-off",
                    "daily",
                    "weekly",
                    "commit",
                    "variance",
                ],
            },
            "measurement": {
                "settings": {
                    "flow_process_duration": 3600,
                    "total_duration": 3600,
                },
                "quotas": { # An empty dictionary here means that no quotas apply
                    "default": 10_000
                }
            },
            "data": {
                "runs": {
                    "retention": 3600,
                },
                "measurements": {
                    "retention": 3600,
                },
                "ci_measurements": {
                    "retention": 3600,
                },
                "hog_measurements": {
                    "retention": 3600,
                },
                "hog_coalitions": {
                    "retention": 3600,
                },
                "hog_tasks": {
                    "retention": 3600,
                },
            },
            "machines": [ # This will be dynamically loaded from the current database
                1,
            ],
            "optimizations": [ # This will be dynamically loaded from the current filesystem
                "container_memory_utilization",
                "container_cpu_utilization",
                "message_optimization",
                "container_build_time",
                "container_boot_time",
                "container_image_size",
            ],
        }

        user = DB().query("""
                INSERT INTO users
                (name, token, capabilities)
                VALUES
                (%s, %s, %s)
                """, params=((name, sha256_hash.hexdigest(), json.dumps(default_capabilities), )))

        return token

class UserAuthenticationError(Exception):
    pass


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('token', help='Please supply a token to get the user')

    args = parser.parse_args()  # script will exit if arguments not present

    authenticated_user_id = User.authenticate(SecureVariable(args.token))
    print("User is", User(authenticated_user_id))
