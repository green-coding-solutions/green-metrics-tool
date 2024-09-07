import os
import string
import re
from schema import Schema, SchemaError, Optional, Or, Use
#
# networks documentation is different than what i see in the wild!
    # name: str
    # also isn't networks optional?
    # fix documentation - name not needed, also netowrks optional
    # add check in runner.py networks parsing, make sure its valid_string
    # is services/type optional?

# services /type missing from documentation?


# https://github.com/compose-spec/compose-spec/blob/master/spec.md

class SchemaChecker():
    def __init__(self, validate_compose_flag):
        self._validate_compose_flag = validate_compose_flag

    def single_or_list(self, value):
        return Or(value, [value])

    def is_valid_string(self, value):
        valid_chars = set(string.ascii_letters + string.digits + '_' + '-')
        if not set(value).issubset(valid_chars):
            raise SchemaError(f"{value} does not use valid characters! (a-zA-Z0-9_-)")

    def contains_no_invalid_chars(self, value):
        bad_values = re.findall(r'(\.\.|\$|\'|"|`|!)', value)
        if bad_values:
            raise SchemaError(f"{value} includes disallowed values: {bad_values}")

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

    def validate_networks_no_invalid_chars(self, networks):
        if isinstance(networks, list):
            for item in networks:
                if item is not None:
                    self.contains_no_invalid_chars(item)
        elif isinstance(networks, dict):
            for key, value in networks.items():
                self.contains_no_invalid_chars(key)
                if value is not None:
                    self.contains_no_invalid_chars(value)
        else:
            raise SchemaError("'networks' should be a list or a dictionary")


    def check_usage_scenario(self, usage_scenario):
        # Anything with Optional() is not needed, but if it exists must conform to the definition specified
        usage_scenario_schema = Schema({
            "name": str,
            "author": str,
            "description": str,

            Optional("networks"): Or(list, dict),

            Optional("services"): {
                Use(self.contains_no_invalid_chars): {
                    Optional("type"): Use(self.valid_service_types),
                    Optional("image"): str,
                    Optional("build"): Or(Or({str:str},list),str),
                    Optional("networks"): self.single_or_list(Use(self.contains_no_invalid_chars)),
                    Optional("environment"): self.single_or_list(Or(dict,str)),
                    Optional("ports"): self.single_or_list(Or(str, int)),
                    Optional("depends_on"): Or([str],dict),
                    Optional("healthcheck"): {
                        Optional('test'): Or(list, str),
                        Optional('interval'): str,
                        Optional('timeout'): str,
                        Optional('retries'): int,
                        Optional('start_period'): str,
                        Optional('start_interval'): str,
                        Optional('disable'): bool,
                    },
                    Optional("setup-commands"): [str],
                    Optional("volumes"): self.single_or_list(str),
                    Optional("folder-destination"):str,
                    Optional("command"): str,
                    Optional("log-stdout"): bool,
                    Optional("log-stderr"): bool,
                    Optional("read-notes-stdout"): bool,
                    Optional("read-sci-stdout"): bool,
                }
            },

            "flow": [{
                "name": str,
                "container": Use(self.contains_no_invalid_chars),
                "commands": [{
                    "type":"console",
                    "command": str,
                    Optional("detach"): bool,
                    Optional("note"): str,
                    Optional("read-notes-stdout"): bool,
                    Optional("read-sci-stdout"): bool,
                    Optional("ignore-errors"): bool,
                    Optional("shell"): str,
                    Optional("log-stdout"): bool,
                    Optional("log-stderr"): bool,
                }],
            }],

            Optional("compose-file"): Use(self.validate_compose_include)
        }, ignore_extra_keys=True)


        # This check is necessary to do in a seperate pass. If tried to bake into the schema object above,
        # it will not know how to handle the value passed when it could be either a dict or list
        if 'networks' in usage_scenario:
            self.validate_networks_no_invalid_chars(usage_scenario['networks'])

        for service_name in usage_scenario.get('services'):
            service = usage_scenario['services'][service_name]
            if 'image' not in service and 'build' not in service:
                raise SchemaError(f"The 'image' key for service '{service_name}' is required when 'build' key is not present.")
            if 'cmd' in service:
                raise SchemaError(f"The 'cmd' key for service '{service_name}' is not supported anymore. Please migrate to 'command'")

        # Ensure that flow names are unique
        flow_names = [flow['name'] for flow in usage_scenario['flow']]
        if len(flow_names) != len(set(flow_names)):
            raise SchemaError("The 'name' field in 'flow' must be unique.")

        for flow in usage_scenario['flow']:
            for command in flow['commands']:
                if  'read-sci-stdout' in command and 'log-stdout' not in command:
                    raise SchemaError(f"You have specified `read-sci-stdout` in flow {flow['name']} but not set `log-stdout` to True.")


        usage_scenario_schema.validate(usage_scenario)


# if __name__ == '__main__':
#     import yaml

#     with open("test-file.yml", encoding='utf8') as f:
#         usage_scenario = yaml.safe_load(f)

#     SchemaChecker = SchemaChecker(validate_compose_flag=True)
#     SchemaChecker.check_usage_scenario(usage_scenario)
