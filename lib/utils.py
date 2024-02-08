import random
import string
import subprocess
import psycopg
import os
from pathlib import Path

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
    data = DB().fetch_one(query, (run_name, ), row_factory=psycopg.rows.dict_row)
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

# This function takes a path and a file and joins them while making sure that no one is trying to escape the
# path with `..`, symbolic links or similar.
# We always return the same error message including the path and file parameter, never `filename` as
# otherwise we might disclose if certain files exist or not.
def join_paths(path, path2, mode='file'):
    filename = os.path.realpath(os.path.join(path, path2))

    # If the original path is a symlink we need to resolve it.
    path = os.path.realpath(path)

    # This is a special case in which the file is '.'
    if filename == path.rstrip('/'):
        return filename

    if not filename.startswith(path):
        raise ValueError(f"{path2} must not be in folder above {path}")

    # To double check we also check if it is in the files allow list

    if mode == 'file':
        folder_content = [str(item) for item in Path(path).rglob("*") if item.is_file()]
    elif mode == 'directory':
        folder_content = [str(item) for item in Path(path).rglob("*") if item.is_dir()]
    else:
        raise RuntimeError(f"Unknown mode supplied for join_paths: {mode}")

    if filename not in folder_content:
        raise ValueError(f"{mode.capitalize()} '{path2}' not in '{path}'")

    # Another way to implement this. This is checking the third time but we want to be extra secure 👾
    if Path(path).resolve(strict=True) not in Path(path, path2).resolve(strict=True).parents:
        raise ValueError(f"{mode.capitalize()} '{path2}' not in folder '{path}'")

    if os.path.exists(filename):
        return filename

    raise FileNotFoundError(f"{path2} in {path} not found")
