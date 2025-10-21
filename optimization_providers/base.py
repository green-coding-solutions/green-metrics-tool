import importlib
from enum import Enum
from lib.db import DB
from pathlib import Path
import asyncio
import aiohttp
import orjson

from lib.global_config import GlobalConfig
from lib import utils
from lib.user import User
from api.scenario_runner import get_run, get_measurements_single, get_network, get_notes, get_phase_stats_single

class Criticality(Enum):
    CRITICAL = 'red'
    MEDIUM = 'orange'
    LOW = 'green'
    INFO = 'blue'

reporters = []

class Reporter:
    def __init__(self, func, tag, criticality, name, icon):
        self.function = func
        self.tag = tag
        self.criticality = criticality
        self.name = name
        self.icon = icon
        self.run_id = None

    def add_optimization(self, title, description, link=None, criticality=None):

        if not criticality:
            criticality =  self.criticality

        return DB().fetch_one("""
            INSERT INTO optimizations
                        (run_id, title, label, criticality, reporter, icon, description, link)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """, params=(self.run_id, title, self.tag, criticality.value, self.name, self.icon, description, link))[0]

    def run(self, *args, **kwargs):
        self.function(self, *args, **kwargs)

def register_reporter(tag, criticality, name, icon, req_providers=None):
    req_providers = [] if req_providers is None else req_providers
    def decorator(func):
        #pylint: disable=global-statement
        reporter = Reporter(func, tag, criticality, name, icon)

        providers = [key.split('.')[-1] for key in utils.get_metric_providers(GlobalConfig().config).keys()]

        if reporter.tag not in ignore_tags and all(item in providers for item in req_providers):
            reporters.append(reporter)

        return reporter
    return decorator

ignore_tags = GlobalConfig().config.get('optimization', {}).get('ignore', [])

if ignore_tags is None: # this is a yml issue when no entry is given but key present
    ignore_tags = []

async def fetch_all_data(run_id):
    # We use the api functions here for multiple reasons.
    # - All logic is in one place
    # - We can query async which is quite a speed increase as most things are sql queries
    # - Detaches the code more so we can split this into a separate module in the future. In theory we could do this over
    #   http as we are looking at the same return data.
    urls = [
        f"{GlobalConfig().config['cluster']['api_url']}/v2/run/{run_id}",
        f"{GlobalConfig().config['cluster']['api_url']}/v1/measurements/single/{run_id}",
        f"{GlobalConfig().config['cluster']['api_url']}/v1/network/{run_id}",
        f"{GlobalConfig().config['cluster']['api_url']}/v1/notes/{run_id}",
        f"{GlobalConfig().config['cluster']['api_url']}/v1/phase_stats/single/{run_id}",
    ]

    async def fetch_url(session, url):
        async with session.get(url) as response:
            return await response.text()

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url(session, url) for url in urls]
        run, measurements, network, notes, phase_stats = await asyncio.gather(*tasks)


    #pylint: disable=no-member
    return orjson.loads(run)['data'], orjson.loads(measurements)['data'], orjson.loads(network)['data'] if network else None, orjson.loads(notes)['data'], orjson.loads(phase_stats)['data']

async def query_all_data(user_id, run_id):
    # This call is used for shared environments, which however cannot access API endpoints.
    # We capture the data via the API functions, but never transmit it via HTTP
    # - All logic stays in one place
    # - We can query async which is quite a speed increase as most things are sql queries
    # - Detaches the code more so we can split this into a separate module in the future. In theory we could do this over
    #   http as we are looking at the same return data.

    user = User(user_id)
    function_calls = [
        get_run(run_id, user),
        get_measurements_single(run_id, user),
        get_network(run_id, user),
        get_notes(run_id, user),
        get_phase_stats_single(run_id, user)
    ]

    run, measurements, network, notes, phase_stats = await asyncio.gather(*function_calls)

    #pylint: disable=no-member
    return (
        orjson.loads(run.body)['data'],
        orjson.loads(measurements.body)['data'],
        orjson.loads(network.body)['data'] if network.body else None, # can be 204 response and thus empty
        orjson.loads(notes.body)['data'],
        orjson.loads(phase_stats.body)['data']
    )


#pylint: disable=dangerous-default-value
def run_reporters(user_id, run_id, repo_path, optimizations_ignore=None):

    if not optimizations_ignore:
        optimizations_ignore = []

    run_data, measurements_data, network_data, notes_data, phase_stats_data = asyncio.run(query_all_data(user_id, run_id))

    for r in reporters:
        if r.tag not in optimizations_ignore:
            print(f"Running {r.tag}")
            r.run_id = run_id
            r.run(run_data, measurements_data, repo_path, network_data, notes_data, phase_stats_data)

def import_reporters():
    # We currently assume that everything is in subdirs. This can be changed later on if we remove the DB() import
    script_dir = Path(__file__).resolve().parent
    for py_file in script_dir.rglob('*.py'):
        if py_file.name == 'base.py':
            continue

        relative_path = py_file.relative_to(script_dir).with_suffix('')
        module_path = f"optimization_providers.{'.'.join(relative_path.parts)}"

        importlib.import_module(module_path)

    print(f"Imported {len(reporters)} optimization reporters")
