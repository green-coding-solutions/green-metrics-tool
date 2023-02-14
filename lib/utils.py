#pylint: disable=no-member
#pylint: disable=invalid-name
import random
import string
import subprocess

from db import DB

def randomword(length):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))

## Is there a better place for this function to live?
def get_pid(project_name):
    query = """
            SELECT
                id
            FROM
                projects
            WHERE name = %s
            """
    data = DB().fetch_one(query, (project_name, ))
    if (data is None or data == []):
        return None

    return data[0]

## Parse a string so that the first letter, and any letter after a _, is capitalized
## E.g. 'foo_bar' -> 'FooBar'
def get_pascal_case(in_string):
    return ''.join([s.capitalize() for s in in_string.split('_')])

def get_metric_providers(config):
    architecture = get_architecture()
    if 'common' in config['measurement']['metric-providers']:
        if config['measurement']['metric-providers']['common'] is None:
            raise RuntimeError('No metric providers under \'common\' key in config.yml')
        if config['measurement']['metric-providers'][architecture] is None:
            raise RuntimeError(f"No metric providers under '{architecture}' key in config.yml")
        metric_providers = {**config['measurement']['metric-providers'][architecture],\
            **config['measurement']['metric-providers']['common']}
    else:
        metric_providers = config['measurement']['metric-providers'][architecture]
    return metric_providers

def get_metric_providers_names(config):
    metric_providers = get_metric_providers(config)
    metric_providers_keys = metric_providers.keys()
    return [(m.split('.')[-1]) for m in metric_providers_keys]

def get_architecture():
    ps = subprocess.run(['uname', '-s'],
            check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, encoding='UTF-8')
    output = ps.stdout.strip().lower()

    if output == 'darwin':
        return 'macos'
    return output
