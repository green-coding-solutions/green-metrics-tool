import os
import string
import re
from schema import Schema, SchemaError, Optional, Or, Use
# https://docs.green-coding.berlin/docs/measuring/usage-scenario/
# networks documentation is different than what i see in the wild!
    # name: str
    # also isn't networks optional?
    # fix documentation - name not needed, also netowrks optional
    # add check in runner.py networks parsing, make sure its valid_string
    # is services/type optional?

# services /type missing from documentation?


# https://github.com/compose-spec/compose-spec/blob/master/spec.md

def single_or_list(value):
    return Or(value, [value])

def is_valid_string(value):
    valid_chars = set(string.ascii_letters + string.digits + '_' + '-')
    if not set(value).issubset(valid_chars):
        raise SchemaError(f"{value} does not use valid characters! (a-zA-Z0-9_-)")

def contains_no_invalid_chars(value):
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

def validate_compose_include(value):
    #!include compose.yml
    # make sure value starts with the string '!include', then space, then a valid yaml file name
    # make sure that compose yaml exists
    if not value.startswith('!include '):
        raise SchemaError(f"{value} does not begin with !include")
    if (not value.endswith('.yml') and not value.endswith('.yaml')):
        raise SchemaError(f"{value} does not end with a valid yaml filename")

    # Extract the filename from the value
    filename = value[len('!include '):]

    # Make sure that the compose yaml exists
    if not os.path.exists(filename):
        raise SchemaError(f"{filename} does not exist")
    return value

def valid_service_types(value):
    if value != 'container':
        raise SchemaError(f"{value} is not 'container'")
    return value

usage_scenario_schema = Schema({
    Optional("name"): str,
    Optional("author"): str,
    Optional("version"): Use(int),

    Optional("networks"): {
       Use(contains_no_invalid_chars): None
    },

    Optional("services"): {
        Use(contains_no_invalid_chars): {
            Optional("type"): Use(valid_service_types),
            "image": str,
            Optional("networks"): single_or_list(Use(contains_no_invalid_chars)),
            Optional("environment"): single_or_list(Or(dict,str)),
            Optional("ports"): single_or_list(Or(str, int)),
            Optional("setup-commands"): [str],
            Optional("volumes"): single_or_list(str),
            Optional("folder-destination"):str,
            Optional("cmd"): str,
        }
    },

    "flow": [{
        "name": str,
        "container": Use(contains_no_invalid_chars),
        "commands": [{
            "type":"console",
            "command": str,
            Optional("detach"): bool,
            Optional("note"): str,
            Optional("read-notes-stdout"): bool,
            Optional("ignore-errors"): bool
        }],
    }],

    Optional("builds"): {
        str:str
    },

    Optional("compose-file"): Use(validate_compose_include)
}, ignore_extra_keys=True)


def check_usage_scenario(usage_scenario):
    usage_scenario_schema.validate(usage_scenario)


# if __name__ == '__main__':

#     with open("test-file.yml", encoding='utf8') as f:
#     # with open("test-file-2.yaml", encoding='utf8') as f:
#         usage_scenario = yaml.safe_load(f)

#     usage_scenario_schema.validate(usage_scenario)
