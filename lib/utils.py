import random
import re
import string
import subprocess
import os
import requests
from urllib.parse import urlparse, urlunparse
from functools import cache
from pathlib import Path

from lib.encryption import encrypt_data, decrypt_data, EncryptionConfigurationError, ENCRYPTED_VALUE_PREFIX

# Matches the userinfo part of a URI that uses HTTP-AUTH, e.g. https://user:pass@host/path
# Username is optional to also catch forms like https://:token@host/path
URI_CREDENTIALS_RE = re.compile(r'([a-zA-Z][a-zA-Z0-9+.\-]*://)[^\s/@:]*(?::[^\s/@]*)?@')

# Matches PEM encoded private key blocks (RSA, EC, OPENSSH, DSA, generic, encrypted, ...)
PRIVATE_KEY_RE = re.compile(r'-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----', re.DOTALL)

REDACTED = '*****GMT-REDACTED*****'

def filter_sensitive_data(text):
    if not text:
        return text
    text = URI_CREDENTIALS_RE.sub(rf'\1{REDACTED}@', text)
    text = PRIVATE_KEY_RE.sub(REDACTED, text)
    return text

# The above are defined before this import as lib.error_helpers imports them back from here (circular import)
from lib import error_helpers
from lib import host_platform
from lib.db import DB

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_test_worker_id():
    # pytest-xdist sets this to 'gw0', 'gw1', ... in each worker process, and leaves it
    # unset when pytest is run without -n (or when not running under pytest at all).
    worker = os.environ.get('PYTEST_XDIST_WORKER')
    if not worker:
        return None
    # Zero-pad the numeric part ('gw1' -> 'gw001') so every worker id this session hands out is
    # the same fixed width. This is the single source of truth every worker-suffixed name
    # (containers, networks, schemas, docker image tags, ...) is built from, so padding it here -
    # once - means none of those downstream consumers can suffer a numeric-prefix collision
    # (e.g. plain substring/prefix matching 'gw1' against 'gw10'..'gw19') without each of them
    # needing their own anchoring logic. 3 digits comfortably covers any realistic worker count.
    match = re.fullmatch(r'gw(\d+)', worker)
    if not match:
        return worker
    return f'gw{int(match.group(1)):03d}'

def container_name(base_name):
    # Suffixed with the pytest-xdist worker id (when running under -n) so that parallel test
    # workers never fight over the same container/network name. Empty outside of pytest-xdist.
    # Single source of truth shared by ScenarioRunner (production naming, lib/scenario_runner.py)
    # and the test suite's own assertions (tests/test_functions.py), so both sides always agree.
    worker_id = get_test_worker_id()
    return f"{base_name}-{worker_id}" if worker_id else base_name

def gmt_tmp_image_name(cleaned_base_name):
    # Same worker-id suffixing as container_name(), but for the '<image>_gmt_run_tmp' docker image
    # tags ScenarioRunner._clean_image_name() builds - a machine-wide, cross-run cache/build-cache
    # resource (unlike containers/networks, it's deliberately reused between separate runs), so
    # without a worker suffix, concurrent workers building the same base image would race on the
    # exact same tag, and host_platform.remove_gmt_tmp_images()'s cache-clearing sweep could rm -f
    # an image another worker is still mid-build/mid-use on. cleaned_base_name must already be
    # through _clean_image_name()'s own charset/lowercase cleanup (or, for test assertions, be a
    # literal that's already known to be clean, e.g. 'alpine'). Single source of truth shared by
    # ScenarioRunner and the test suite's own assertions, so both sides always agree.
    worker_id = get_test_worker_id()
    name = f"{cleaned_base_name}_gmt_run_tmp"
    return f"{name}_{worker_id}" if worker_id else name

def remove_git_suffix(url):
    if url.endswith('.git'):
        return url[:-4]
    return url

def _get_uri_userinfo(parsed_uri):
    """
    Rebuild the raw 'user:pass' (or 'user') userinfo string of an already-parsed URI.
    Returns None if the URI carried no credentials.
    """
    if not (parsed_uri.username or parsed_uri.password):
        return None
    return f"{parsed_uri.username or ''}:{parsed_uri.password}" if parsed_uri.password else (parsed_uri.username or '')

def _set_uri_userinfo(parsed_uri, userinfo):
    host = parsed_uri.hostname or ''
    if parsed_uri.port:
        host += f":{parsed_uri.port}"
    netloc = f"{userinfo}@{host}" if userinfo else host
    return urlunparse((parsed_uri.scheme, netloc, parsed_uri.path, parsed_uri.params, parsed_uri.query, parsed_uri.fragment))

def strip_uri_userinfo(uri):
    """
    Split a URI into a credential-free URI and its raw userinfo ('user:pass' or 'user').
    Returns (clean_uri, userinfo), where userinfo is None if the URI carried no credentials.
    """
    parsed_uri = urlparse(uri)
    userinfo = _get_uri_userinfo(parsed_uri)
    if userinfo is None:
        return uri, None

    return _set_uri_userinfo(parsed_uri, None), userinfo

def inject_uri_userinfo(uri, userinfo):
    """
    Embed a raw 'user:pass' (or 'user') userinfo string into a URI, replacing any userinfo already present.
    Returns the URI unchanged if userinfo is falsy.
    """
    if not userinfo:
        return uri
    return _set_uri_userinfo(urlparse(uri), userinfo)

def encrypt_uri_credentials(uri):
    """
    Strip credentials off a URI and re-embed them encrypted, for safe storage in the DB.
    Returns the URI unchanged if it carries no credentials.
    Raises EncryptionConfigurationError (from lib.encryption) if credentials are present but no
    encryption key is configured.
    """
    clean_uri, userinfo = strip_uri_userinfo(uri)
    if userinfo is None:
        return uri
    return inject_uri_userinfo(clean_uri, encrypt_data(userinfo))

def decrypt_userinfo(userinfo):
    """
    Decrypt a userinfo string (as previously returned by strip_uri_userinfo, possibly encrypted
    via encrypt_uri_credentials) if it carries the encrypted-value prefix; otherwise return it
    unchanged. Returns None if userinfo is falsy.

    Deliberately does NOT re-embed the result into a URI: putting credentials back into a URI
    that is then passed as a subprocess argument (e.g. to git) leaks them to any local user via
    `ps` or `/proc/<pid>/cmdline`. Callers needing to authenticate a subprocess should instead
    split the result with split_userinfo() and pass the parts via environment variables or a
    credential helper (see ScenarioRunner._get_git_environment).
    """
    if not userinfo:
        return None
    if userinfo.startswith(ENCRYPTED_VALUE_PREFIX):
        return decrypt_data(userinfo)
    return userinfo

def split_userinfo(userinfo):
    """
    Split a raw 'user:pass' or 'user' userinfo string (as returned by strip_uri_userinfo or
    decrypt_userinfo) into (username, password). Both are '' if userinfo is falsy; password is
    '' if userinfo has no ':'.
    """
    if not userinfo:
        return '', ''
    username, _, password = userinfo.partition(':')
    return username, password

def get_git_api(parsed_url):

    if parsed_url.netloc == '' and '@' in parsed_url.path: # this could be an SSH git shorthand, we allow this but cannot determine API
        return [None, None]

    hostname = parsed_url.hostname or ''

    if hostname in ['github.com', 'www.github.com']:
        return [f"https://api.github.com/repos/{remove_git_suffix(parsed_url.path.strip(' /'))}", 'github']

    if hostname in ['gitlab.com', 'www.gitlab.com']:
        return [f"https://gitlab.com/api/v4/projects/{parsed_url.path.strip(' /').replace('/', '%2F')}/repository", 'gitlab']

    # Alternative:

    # assume gitlab private hosted
    api_host = hostname
    if parsed_url.port:
        api_host += f":{parsed_url.port}"

    # repo_url can come from watchlist rows, where it is stored with its userinfo encrypted
    # (see encrypt_uri_credentials) - decrypt it back to real credentials before using it as
    # Basic auth, otherwise the ciphertext itself would be sent to the git host and rejected.
    try:
        userinfo = decrypt_userinfo(_get_uri_userinfo(parsed_url))
    except EncryptionConfigurationError as exc:
        raise RuntimeError(f"Cannot authenticate against {hostname}: stored credentials are encrypted but no decryption key is configured on this server") from exc

    if userinfo is not None:
        api_host = f"{userinfo}@{api_host}"
    return [f"https://{api_host}/api/v4/projects/{parsed_url.path.strip(' /').replace('/', '%2F')}/repository", 'custom']


def check_repo(repo_url, branch='main'):
    parsed_url = urlparse(repo_url)
    [url, git_api] = get_git_api(parsed_url)
    if git_api == 'github':
        url = f"{url}/commits?per_page=1&sha={branch}"
    elif git_api in ('gitlab', 'custom'):
        url = f"{url}/commits?per_page=1"
    else:
        error_helpers.log_error('Unknown git repo type detected. Skipping further validation for now.',repo_url=repo_url)
        return

    try:
        response = requests.get(url, timeout=10)
    except Exception as exc:
        error_helpers.log_error(f"Request to {git_api} API failed",url=url,exception=str(exc))
        raise RuntimeError(f"Could not find repository {repo_url} and branch {branch}. Is the repo publicly accessible, not empty and does the branch {branch} exist?") from exc

    if response.status_code == 200:
        return

    message = _extract_api_message(response)

    # ---- Rate limit detection (works even on 403) ----
    if response.status_code == 403 and isinstance(message, str) and message.startswith("API rate limit exceeded"):
        error_helpers.log_error(f"{git_api} rate limit exceeded while accessing {repo_url}. Skipping repo validation - Consider authenticating future requests.")
        return

    # We early return here in case of custom API and only do a warning,
    # bc often times the SSH or token which might be supplied in the URL is too restrictive then and cannot be used to query the commits also
    # However we must check the commits endpoint bc this tells us if the repo is non empty or not
    if git_api == 'custom':
        error_helpers.log_error(f"Connect to {git_api} API was possible, but return code was not 200",url=url,status_code=response.status_code,status_text=response.text)
        return

    if response.status_code == 403:
        raise PermissionError(
            f"Access denied (403) for repository {repo_url}. "
            f"Repo may be private or credentials are insufficient."
        )

    if response.status_code == 404:
        ssh_hint = ''
        if parsed_url.scheme in ('http', 'https'):
            ssh_hint = ' If this is a private repository, use the SSH URL (e.g. git@github.com:owner/repo.git) instead of the HTTPS URL, and configure an SSH key in your account settings.'
        raise RuntimeError(f"Could not find repository {repo_url} and branch {branch}. Is the repo publicly accessible, not empty and does the branch {branch} exist?{ssh_hint}")

    raise RuntimeError(f"Repository returned bad status code ({response.status_code}). Is the repo ({repo_url}) publicly accessible, not empty and does the branch {branch} exist?")

def _extract_api_message(response):
    try:
        data = response.json()
        return data.get("message", "") if isinstance(data, dict) else ""
    except Exception: # pylint: disable=broad-exception-caught
        return response.text or ""

def get_repo_last_marker(repo_url, marker, branch=None):

    parsed_url = urlparse(repo_url)
    [url, git_api] = get_git_api(parsed_url)

    if marker == 'tags':
        access_key = 'name' if git_api == 'github' else 'name'
    elif marker == 'commits':
        access_key = 'sha' if git_api == 'github' else 'id'
    else:
        raise ValueError(f"Calling get_repo_last_marker with unknown marker: {marker}")

    url = f"{url}/{marker}?per_page=1"
    if branch:
        if git_api == 'github':
            url += f"&sha={branch}"
        elif git_api in ('gitlab', 'custom'):
            url += f"&ref_name={branch}"

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
    if host_platform.is_windows():
        raise RuntimeError('get_network_interfaces is not supported on Windows hosts')

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

SENSITIVE_CONFIG_KEYS = frozenset({
    'token',
    'electricity_maps_token',
    'password',
    'secret',
    'api_key',
    'auth_token',
})

def sanitize_config(value, _redacted='__REDACTED__'):
    if isinstance(value, dict):
        return {
            k: _redacted if isinstance(k, str) and k.lower() in SENSITIVE_CONFIG_KEYS else sanitize_config(v, _redacted)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [sanitize_config(item, _redacted) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_config(item, _redacted) for item in value)
    return value

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
    return host_platform.get_architecture_name()


def is_rapl_energy_filtering_deactivated():
    python_realpath = Path('/usr/bin/python3').resolve(strict=True) # bc typically symlinked to python3.12 or similar
    result = subprocess.run(['sudo', python_realpath.as_posix(), '-I', '-B', '-S', Path('/usr/local/bin/green-metrics-tool/hardware_info_root.py').resolve(strict=True).as_posix(), '--read-rapl-energy-filtering'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            cwd=os.path.abspath(os.path.join(CURRENT_DIR, '..')),
                            check=True, encoding='UTF-8', errors='replace')
    return '1' != result.stdout.strip()

def normalize_timestamp(time_str):
    # we use microsecond timestamps internally
    # some outputs give us second, millisecond or nanosecond ... so we normalize those
    length = len(time_str)

    # Important: Before we had here a 10,19 timestamp and where upgrading it from second to
    # microsecond precision. This lead to errors in correct phase attribution by ghosting into previous phases
    # Timing must be at least microsecond precision
    if length < 16 or length > 19:
        raise ValueError(f"Invalid time string length: {length} for time string: {time_str}. Must be between 16 and 19 characters.")

    return time_str.ljust(16,'0')[:16] # Pad with spaces on the right and Truncate to 16 characters. no ifs and counting ... just do.

@cache
def find_own_cgroup_name():
    if host_platform.is_windows():
        raise RuntimeError('Cgroup detection is not supported on Windows hosts')

    current_pid = os.getpid()
    with open(f"/proc/{current_pid}/cgroup", 'r', encoding='utf-8', errors='replace') as file:
        lines = file.readlines()
        found_cgroups = len(lines)
        if found_cgroups != 1:
            raise RuntimeError(f"Could not find GMT\'s own cgroup or found too many. Amount: {found_cgroups}")
        return lines[0].split('/')[-1].strip()


def runtime_dir():
    if host_platform.is_windows():
        return os.environ.get("TEMP") or os.environ.get("TMP") or str(host_platform.get_tmp_root())

    uid = os.getuid()

    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg and os.access(xdg, os.W_OK):
        return xdg

    run_user = f"/run/user/{uid}"
    if os.path.isdir(run_user) and os.access(run_user, os.W_OK):
        return run_user

    return "/tmp"
