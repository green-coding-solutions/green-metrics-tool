import random
import string
import subprocess

from lib.db import DB

def randomword(length):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))

def get_run_data(run_name):
    query = """
            SELECT
                *
            FROM
                runs
            WHERE name = %s
            """
    data = DB().fetch_one(query, (run_name, ), fetch_mode='dict')
    if data is None or data == []:
        return None
    return data

## Parse a string so that the first letter, and any letter after a _, is capitalized
## E.g. 'foo_bar' -> 'FooBar'
def get_pascal_case(in_string):
    return ''.join([s.capitalize() for s in in_string.split('_')])

def get_metric_providers(config):
    architecture = get_architecture()

    if 'metric-providers' not in config['measurement'] or config['measurement']['metric-providers'] is None:
        raise RuntimeError('You must set the "metric-providers" key under \
            "measurement" and set at least one provider.')

    # we are checking for none, since we believe that YAML parsing can never return an empty list
    # which should also be checked for then
    if architecture not in config['measurement']['metric-providers'] or \
            config['measurement']['metric-providers'][architecture] is None:
        metric_providers = {}
    else:
        metric_providers = config['measurement']['metric-providers'][architecture]

    if 'common' in config['measurement']['metric-providers']:
        if config['measurement']['metric-providers']['common'] is not None:
            metric_providers = {**metric_providers, **config['measurement']['metric-providers']['common']}

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
