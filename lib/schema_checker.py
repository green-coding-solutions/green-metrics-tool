import os
import string
import re
from schema import Schema, SchemaError, Optional, Or, Use, And, Regex
from datetime import datetime

# https://github.com/compose-spec/compose-spec/blob/master/spec.md

class SchemaChecker():
    def __init__(self, validate_compose_flag):
        self._validate_compose_flag = validate_compose_flag

    def is_valid_string(self, value):
        valid_chars = set(string.ascii_letters + string.digits + '_' + '-')
        if not set(value).issubset(valid_chars):
            raise SchemaError(f"{value} does not use valid characters! (a-zA-Z0-9_-)")
        return value

    def contains_no_invalid_chars(self, value):
        bad_values = re.findall(r'(\.\.|\$|\'|"|`|!)', value)
        if bad_values:
            raise SchemaError(f"{value} includes disallowed values: {bad_values}")
        return value

    def not_empty(self, value):
        if value.strip() == '':
            raise SchemaError('Value cannot be empty')
        return value

    ## If we ever want smarter validation for ports, here's a list of examples that we need to support:
    # - 3000
    # - 3000-3005
    # - 8000:8000
    # - 9090-9091:8080-8081
    # - 49100:22
    # - 8000-9000:80
    # - 127.0.0.1:8001:8001
    # - 127.0.0.1:5000-5010:5000-5010
    # - 6060:6060/udp

    def validate_compose_include(self, value):
        #!include compose.yml
        # make sure value starts with the string '!include', then space, then a valid yaml file name
        # make sure that compose yaschemaml exists
        if not value.startswith('!include '):
            raise SchemaError(f"{value} does not begin with !include")
        if (not value.endswith('.yml') and not value.endswith('.yaml')):
            raise SchemaError(f"{value} does not end with a valid yaml filename")

        if self._validate_compose_flag is True:
            # Extract the filename from the value
            filename = value[len('!include '):]

            # Make sure that the compose yaml exists
            if not os.path.exists(filename):
                raise SchemaError(f"{filename} does not exist")

        return value

    def valid_service_types(self, value):
        if value != 'container':
            raise SchemaError(f"{value} is not 'container'")
        return value


    def validate_networks_no_invalid_chars(self, value):
        if isinstance(value, list):
            for item in value:
                if item is not None:
                    self.contains_no_invalid_chars(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                self.contains_no_invalid_chars(key)
                if item and 'internal' in item:
                    if not isinstance(item['internal'], bool):
                        raise SchemaError("networks modifier 'internal' must be boolean")
        else:
            raise SchemaError("'networks' should be a list or a dictionary")

        return value

    def check_usage_scenario(self, usage_scenario):
        # Anything with Optional() is not needed, but if it exists must conform to the definition specified
        usage_scenario_schema = Schema({
            'name': str,
            'author': And(str, Use(self.not_empty)),
            'description': And(str, Use(self.not_empty)),
            Optional('ignore-unsupported-compose'): bool,
            Optional('version'): Or(str, int, float, datetime), # is part of compose. we ignore it as it is non functionaly anyway
            Optional('architecture'): And(str, Use(self.not_empty)),
            Optional('sci'): {
                'R_d': And(str, Use(self.not_empty)),
            },

            Optional('networks'): Or(
                dict,
                [And(str, Use(self.contains_no_invalid_chars))],
            ),
            Optional('volumes'): Or(
                dict,
                And(str, Use(self.contains_no_invalid_chars))
            ),
            Optional('services'): {
                Use(self.contains_no_invalid_chars): {
                    Optional('restart'): str, # is part of compose. we ignore it as GMT has own orchestration
                    Optional('expose'): [str, int], # is part of compose. we ignore it as it is non functionaly anyway
                    Optional('init'): bool,
                    Optional('type'): Use(self.valid_service_types),
                    Optional('image'): And(str, Use(self.not_empty)),
                    Optional('build'): Or(Or({And(str, Use(self.not_empty)):And(str, Use(self.not_empty))},list),And(str, Use(self.not_empty))),
                    Optional('networks'): Or(
                        [And(str, Use(self.contains_no_invalid_chars))],
                        {
                            Use(self.contains_no_invalid_chars):
                                Or(
                                    None,
                                    { 'aliases': [Use(self.contains_no_invalid_chars)] }
                                )
                        }
                    ),
                    Optional('environment'): Or(
                        dict,
                        [And(str, Use(self.not_empty))]
                    ),
                    Optional('labels'): Or(
                        dict,
                        [And(str, Use(self.not_empty))]
                    ),
                    Optional('ports'): [Or( # we do not support the long form as mappings
                        int,
                        And(str, Use(self.not_empty))
                    )],
                    Optional('depends_on'): Or(
                        dict,
                        [And(str, Use(self.not_empty))]
                    ),
                    Optional('deploy'):Or({
                        Optional('resources'): {
                            Optional('limits'): {
                                Optional('cpus'): Or(And(str, Use(self.not_empty)), float, int),
                                Optional('memory') : Or(And(str, Use(self.not_empty)), float, int),
                            }
                        }
                    }, None),
                    Optional('mem_limit'): Or(And(str, Use(self.not_empty)), float, int),
                    Optional('cpus') : Or(And(str, Use(self.not_empty)), float, int),
                    Optional('container_name'): And(str, Use(self.not_empty)),
                    Optional('shm_size'): Or(And(str, Use(self.not_empty)), float, int),
                    Optional('healthcheck'): {
                        Optional('test'): Or(list, And(str, Use(self.not_empty))),
                        Optional('interval'): And(str, Use(self.not_empty)),
                        Optional('timeout'): And(str, Use(self.not_empty)),
                        Optional('retries'): int,
                        Optional('start_period'): And(str, Use(self.not_empty)),
                        Optional('start_interval'): And(str, Use(self.not_empty)),
                        Optional('disable'): bool,
                    },
                    Optional('setup-commands'): [{
                        'command': And(str, Use(self.not_empty)),
                        Optional('detach'): bool,
                        Optional('shell'): And(str, Use(self.not_empty)),
                    }],
                    Optional('volumes'): [And(str, Use(self.not_empty))],
                    Optional('folder-destination'):And(str, Use(self.not_empty)),
                    Optional('entrypoint'): Or(str, [str]), # can be empty!
                    Optional('command'): Or(And(str, Use(self.not_empty)), [And(str, Use(self.not_empty))]),
                    Optional('log-stdout'): bool,
                    Optional('log-stderr'): bool,
                    Optional('read-notes-stdout'): bool,
                    Optional('read-sci-stdout'): bool,
                    Optional('docker-run-args'): [And(str, Use(self.not_empty))],

                }
            },

             'flow': [{
                'name': And(str, Use(self.not_empty), Regex(r'^[\.\s0-9a-zA-Z_\(\)-]+$')),
                'container': And(str, Use(self.not_empty), Use(self.contains_no_invalid_chars)),
                'commands': [{
                    'type': Or('console', 'playwright'),
                    'command': And(str, Use(self.not_empty)),
                    Optional('detach'): bool,
                    Optional('note'): And(str, Use(self.not_empty)),
                    Optional('read-notes-stdout'): bool,
                    Optional('read-sci-stdout'): bool,
                    Optional('ignore-errors'): bool,
                    Optional('shell'): And(str, Use(self.not_empty)),
                    Optional('log-stdout'): bool,
                    Optional('stream-stdout'): bool,
                    Optional('log-stderr'): bool,
                    Optional('stream-stderr'): bool,
                }],

            }],

            Optional('compose-file'): Use(self.validate_compose_include)
        }, ignore_extra_keys=bool(usage_scenario.get('ignore-unsupported-compose', False)))

        # First we check the general structure. Otherwise we later cannot even iterate over it
        try:
            usage_scenario_schema.validate(usage_scenario)
        except SchemaError as e: # This block filters out the too long error message that include the parsing structure

            error_message = e.autos

            if len(e.autos) >= 3:
                error_message = e.autos[2:]

            if 'Wrong key' in e.code:
                raise SchemaError(f"Your compose file does contain a key that GMT does not support - Please check if the container will still run as intended. If you want to ignore this error you can add the attribute `ignore-unsupported-compose: true` to your usage_scenario.yml\nError: {error_message}") from e

            raise SchemaError(error_message) from e


        # This check is necessary to do in a seperate pass. If tried to bake into the schema object above,
        # it will not know how to handle the value passed when it could be either a dict or list
        if 'networks' in usage_scenario:
            self.validate_networks_no_invalid_chars(usage_scenario['networks'])

        known_container_names = []
        for service_name, service in usage_scenario.get('services', {}).items():
            if 'container_name' in service:
                container_name = service['container_name']
            else:
                container_name = service_name

            if container_name in known_container_names:
                raise SchemaError(f"Container name '{container_name}' was already used. Please choose unique container names.")
            known_container_names.append(container_name)

            if 'image' not in service and 'build' not in service:
                raise SchemaError(f"The 'image' key for service '{service_name}' is required when 'build' key is not present.")
            if 'cmd' in service:
                raise SchemaError(f"The 'cmd' key for service '{service_name}' is not supported anymore. Please migrate to 'command'")


            if (cpus := service.get('cpus')) and (cpus_deploy := service.get('deploy', {}).get('resources', {}).get('limits', {}).get('cpus')):
                if cpus != cpus_deploy:
                    raise SchemaError('cpus service top level key and deploy.resources.limits.cpus must be identical')

            if (mem_limit := service.get('mem_limit')) and (mem_limit_deploy := service.get('deploy', {}).get('resources', {}).get('limits', {}).get('memory')):
                if mem_limit != mem_limit_deploy:
                    raise SchemaError('mem_limit service top level key and deploy.resources.limits.memory must be identical')

        known_flow_names = []
        for flow in usage_scenario['flow']:
            if flow['name'] in known_flow_names:
                raise SchemaError(f"The 'name' field in 'flow' must be unique. '{flow['name']}' was already used.")
            known_flow_names.append(flow['name'])

            for command in flow['commands']:
                if command.get('read-sci-stdout', False) and command.get('log-stdout', True): # log-stdout is by default always on. This is why we set default to True
                    raise SchemaError(f"You have specified `read-sci-stdout` in flow {flow['name']} but not set `log-stdout` to True.")

                if command.get('read-notes-stdout', False) and command.get('log-stdout', True): # log-stdout is by default always on. This is why we set default to True
                    raise SchemaError(f"You have specified `read-notes-stdout` in flow {flow['name']} but not set `log-stdout` to True.")


# if __name__ == '__main__':
#     import yaml

#     with open("test-file.yml", encoding='utf8') as f:
#         usage_scenario = yaml.safe_load(f)

#     SchemaChecker = SchemaChecker(validate_compose_flag=True)
#     SchemaChecker.check_usage_scenario(usage_scenario)
