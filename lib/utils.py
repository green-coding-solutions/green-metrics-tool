import random
import string
import subprocess
import os
import requests
from urllib.parse import urlparse
from fastapi.exceptions import RequestValidationError

from lib import error_helpers
from lib.db import DB

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_git_api(parsed_url):

    if parsed_url.netloc in ['github.com', 'www.github.com']:
        return [f"https://api.github.com/repos/{parsed_url.path.strip(' /')}", 'github']

    if parsed_url.netloc in ['gitlab.com', 'www.gitlab.com']:
        return [f"https://gitlab.com/api/v4/projects/{parsed_url.path.strip(' /').replace('/', '%2F')}/repository", 'gitlab']

    # assume gitlab private hosted
    return [f"{parsed_url.scheme}://{parsed_url.netloc}/api/v4/projects/{parsed_url.path.strip(' /').replace('/', '%2F')}/repository", 'gitlab']


def check_repo(repo_url, branch='main'):
    parsed_url = urlparse(repo_url)
    [url, git_api] = get_git_api(parsed_url)
    if git_api == 'github':
        url = f"{url}/commits?per_page=1&sha={branch}"
    else:
        url = f"{url}/commits?per_page=1"

    try:
        response = requests.get(url, timeout=10)
    except Exception as exc:
        error_helpers.log_error('Request to GitHub API failed',url=url,exception=str(exc))
        raise RequestValidationError(f"Could not find repository {repo_url} and branch {branch}. Is the repo publicly accessible, not empty and does the branch {branch} exist?") from exc

    if response.status_code != 200:
        error_helpers.log_error('Request to GitHub API failed',url=url,status_code=response.status_code,status_text=response.text)
        raise RequestValidationError(f"Could not find repository {repo_url} and branch {branch}. Is the repo publicly accessible, not empty and does the branch {branch} exist?")

def get_repo_last_marker(repo_url, marker):

    parsed_url = urlparse(repo_url)
    [url, git_api] = get_git_api(parsed_url)

    if marker == 'tags':
        access_key = 'name' if git_api == 'github' else 'name'
    elif marker == 'commits':
        access_key = 'sha' if git_api == 'github' else 'id'
    else:
        raise ValueError(f"Calling get_repo_last_marker with unknown marker: {marker}")

    url = f"{url}/{marker}?per_page=1"

    try:
        response = requests.get(url, timeout=10)
    except Exception as exc:
        error_helpers.log_error('Request to GitHub API failed',url=url,exception=str(exc))
        raise RequestValidationError(f"Could not find repository {repo_url}. Is the repository publicly accessible and not empty?") from exc

    if response.status_code != 200:
        error_helpers.log_error('Request to GitHub API failed',url=url,status_code=response.status_code,status_text=response.text)
        raise RequestValidationError(f"Could not find repository {repo_url} - Is the repository public and a GitHub or GitLab repository?")
    data = response.json()
    if not data:
        return None
    return data[0][access_key] # We assume it is sorted DESC

def get_timeline_project(repo_url):
    query = """
            SELECT
                *
            FROM
                timeline_projects
            WHERE url = %s
            """
    data = DB().fetch_one(query, (repo_url, ), fetch_mode='dict')
    if data is None or data == []:
        return None
    return data


# for pandas dataframes that are grouped and diffed
def df_fill_mean(group):
    group.iloc[0] = group.mean(skipna=True)
    return group


def get_network_interfaces(mode='all'):
    # Path to network interfaces in sysfs
    sysfs_net_path = '/sys/class/net'

    if mode not in ['all', 'virtual', 'physical']:
        raise RuntimeError('get_network_interfaces supports only all, virtual and physical')

    # List all interfaces in /sys/class/net
    interfaces = os.listdir(sysfs_net_path)
    selected_interfaces = []

    for interface in interfaces:
        # Check if the interface is not a virtual one
        # Virtual interfaces typically don't have a device directory or are loopback
        if mode == 'all':
            selected_interfaces.append(interface)
        else:
            device_path = os.path.join(sysfs_net_path, interface, 'device')
            if mode == 'physical' and os.path.exists(device_path):  # If the 'device' directory exists, it's a physical device
                selected_interfaces.append(interface)
            elif mode == 'virtual' and not os.path.exists(device_path):  # If the 'device' directory exists, it's a physical device
                selected_interfaces.append(interface)

    return selected_interfaces

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


def is_rapl_energy_filtering_deactivated():
    result = subprocess.run(['sudo', 'python3', '-m', 'lib.hardware_info_root', '--read-rapl-energy-filtering'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            cwd=os.path.abspath(os.path.join(CURRENT_DIR, '..')),
                            check=True, encoding='UTF-8')
    return '1' != result.stdout.strip()
