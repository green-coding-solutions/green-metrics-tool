import random
import string
import subprocess
import os
import requests
from urllib.parse import urlparse
from functools import cache

from lib import error_helpers
from lib.db import DB

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

def is_outside_symlink(base_dir, symlink_path):
    try:
        abs_target = os.path.realpath(symlink_path)
        return not abs_target.startswith(os.path.realpath(base_dir)), abs_target
    except OSError:
        return False, None  # Not a symlink

def find_outside_symlinks(base_dir):
    for root, dirs, files in os.walk(base_dir):
        for name in dirs + files:
            full_path = os.path.join(root, name)
            is_outside, target = is_outside_symlink(base_dir, full_path)
            if is_outside:
                return f"{full_path} → {target}"
    return None

def remove_git_suffix(url):
    if url.endswith('.git'):
        return url[:-4]
    return url

def get_git_api(parsed_url):

    if parsed_url.netloc == '' and '@' in parsed_url.path: # this could be an SSH git shorthand, we allow this but cannot determine API
        return [None, None]

    if parsed_url.netloc in ['github.com', 'www.github.com']:
        return [f"https://api.github.com/repos/{remove_git_suffix(parsed_url.path.strip(' /'))}", 'github']

    if parsed_url.netloc in ['gitlab.com', 'www.gitlab.com']:
        return [f"https://gitlab.com/api/v4/projects/{parsed_url.path.strip(' /').replace('/', '%2F')}/repository", 'gitlab']

    # Alternative:

    # assume gitlab private hosted
    return [f"https://{parsed_url.netloc}/api/v4/projects/{parsed_url.path.strip(' /').replace('/', '%2F')}/repository", 'gitlab-custom']


def check_repo(repo_url, branch='main'):
    parsed_url = urlparse(repo_url)
    [url, git_api] = get_git_api(parsed_url)
    if git_api == 'github':
        url = f"{url}/commits?per_page=1&sha={branch}"
    elif git_api in ('gitlab', 'gitlab-custom'):
        url = f"{url}/commits?per_page=1"
    else:
        error_helpers.log_error('Unknown git repo type detected. Skipping further validation for now.',repo_url=repo_url)
        return

    try:
        response = requests.get(url, timeout=10)
    except Exception as exc:
        error_helpers.log_error(f"Request to {git_api} API failed",url=url,exception=str(exc))
        raise RuntimeError(f"Could not find repository {repo_url} and branch {branch}. Is the repo publicly accessible, not empty and does the branch {branch} exist?") from exc

    # We do not fail here, but only do a warning, bc often times the SSH or token which might be supplied in the URL is too restrictive then and cannot be used to query the commits also
    # However we do check the commits endpoint bc this tells us if the repo is non empty or not
    if response.status_code != 200:
        if git_api in ('gitlab', 'github'):
            raise RuntimeError(f"Repository returned bad status code ({response.status_code}). Is the repo ({repo_url}) publicly accessible, not empty and does the branch {branch} exist?")
        else:
            error_helpers.log_error(f"Connect to {git_api} API was possible, but return code was not 200",url=url,status_code=response.status_code,status_text=response.text)

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
        raise RuntimeError(f"Could not find repository {repo_url}. Is the repository publicly accessible and not empty?") from exc

    if response.status_code != 200:
        error_helpers.log_error('Request to GitHub API failed',url=url,status_code=response.status_code,status_text=response.text)
        raise RuntimeError(f"Could not find repository {repo_url} - Is the repository public and a GitHub or GitLab repository?")
    data = response.json()
    if not data:
        return None
    return data[0][access_key] # We assume it is sorted DESC

def get_watchlist_item(repo_url):
    query = """
            SELECT
                *
            FROM
                watchlist
            WHERE repo_url = %s
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

def get_metric_providers(config, disabled_metric_providers=None):
    architecture = get_architecture()

    if 'metric_providers' not in config['measurement'] or config['measurement']['metric_providers'] is None:
        raise RuntimeError('You must set the "metric_providers" key under \
            "measurement" and set at least one provider.')

    # we are checking for none, since we believe that YAML parsing can never return an empty list
    # which should also be checked for then
    if architecture not in config['measurement']['metric_providers'] or \
            config['measurement']['metric_providers'][architecture] is None:
        metric_providers = {}
    else:
        metric_providers = config['measurement']['metric_providers'][architecture]

    if 'common' in config['measurement']['metric_providers']:
        if config['measurement']['metric_providers']['common'] is not None:
            metric_providers = {**metric_providers, **config['measurement']['metric_providers']['common']}

    if disabled_metric_providers:
        metric_providers = {key: value for key, value in metric_providers.items() if key.rsplit('.', maxsplit=1)[-1] not in disabled_metric_providers}

    return metric_providers

def get_metric_providers_names(config):
    metric_providers = get_metric_providers(config)
    metric_providers_keys = metric_providers.keys()
    return [(m.split('.')[-1]) for m in metric_providers_keys]

def get_architecture():
    ps = subprocess.run(['uname', '-s'],
            check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, encoding='UTF-8', errors='replace')
    output = ps.stdout.strip().lower()

    if output == 'darwin':
        return 'macos'
    return output


def is_rapl_energy_filtering_deactivated():
    result = subprocess.run(['sudo', 'python3', '-m', 'lib.hardware_info_root', '--read-rapl-energy-filtering'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            cwd=os.path.abspath(os.path.join(CURRENT_DIR, '..')),
                            check=True, encoding='UTF-8', errors='replace')
    return '1' != result.stdout.strip()

@cache
def find_own_cgroup_name():
    current_pid = os.getpid()
    with open(f"/proc/{current_pid}/cgroup", 'r', encoding='utf-8', errors='replace') as file:
        lines = file.readlines()
        found_cgroups = len(lines)
        if found_cgroups != 1:
            raise RuntimeError(f"Could not find GMT\'s own cgroup or found too many. Amount: {found_cgroups}")
        return lines[0].split('/')[-1].strip()


def runtime_dir():
    uid = os.getuid()

    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg and os.access(xdg, os.W_OK):
        return xdg

    run_user = f"/run/user/{uid}"
    if os.path.isdir(run_user) and os.access(run_user, os.W_OK):
        return run_user

    return "/tmp"
