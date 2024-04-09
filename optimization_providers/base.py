import importlib
from enum import Enum
from lib.db import DB
from pathlib import Path
import asyncio

from lib.global_config import GlobalConfig
from lib import utils

from api.main import get_measurements_single, get_network, get_notes, get_phase_stats_single, get_run

class Criticality(Enum):
    CRITICAL = 'red'
    MEDIUM = 'orange'
    LOW = 'green'
    INFO = 'blue'

reporters = []

keep_files = False

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

def register_reporter(tag, criticality, name, icon, need_files=False, req_providers=None):
    req_providers = [] if req_providers is None else req_providers
    def decorator(func):
        #pylint: disable=global-statement
        global keep_files
        reporter = Reporter(func, tag, criticality, name, icon)

        providers = [key.split('.')[-1] for key in utils.get_metric_providers(GlobalConfig().config).keys()]

        if reporter.tag not in ignore_tags and all(item in providers for item in req_providers):
            reporters.append(reporter)
            if need_files:
                keep_files = True

        return reporter
    return decorator

ignore_tags = GlobalConfig().config.get('optimization', {}).get('ignore', [])

async def fetch_all_data(run_id):
    # We use the api functions here for multiple reasons.
    # - All logic is in one place
    # - We can query async which is quite a speed increase as most things are sql queries
    # - Detaches the code more so we can split this into a separate module in the future. In theory we could do this over
    #   http as we are looking at the same return data.
    run, measurements, network, notes, phase = await asyncio.gather(
        get_run(run_id),
        get_measurements_single(run_id),
        get_network(run_id),
        get_notes(run_id),
        get_phase_stats_single(run_id)
    )

    for obj in [run, measurements, network, notes, phase]:
        if obj.status_code == 204:
            obj.content = {
                'success': True,
                'data': []
            }

    if run.content['success'] and measurements.content['success'] and network.content['success'] \
            and notes.content['success'] and phase.content['success']:
        run_data = run.content['data']
        measurements_data = measurements.content['data']
        network_data = network.content['data']
        notes_data = notes.content['data']
        phase_data = phase.content['data']
    else:
        raise RuntimeError('Getting data from the API failed', run, measurements, network, notes, phase)

    return run_data, measurements_data, network_data, notes_data, phase_data

#pylint: disable=dangerous-default-value
def run_reporters(run_id, repo_path, optimizations_ignore=[]):

    run_data, measurements_data, network_data, notes_data, phase_data = asyncio.run(fetch_all_data(run_id))

    for r in reporters:
        if r.tag not in optimizations_ignore:
            print(f"Running {r.tag}")
            r.run_id = run_id
            r.run(run_data, measurements_data, repo_path, network_data, notes_data, phase_data)

def import_reporters():
    # We currently assume that everything is in subdirs. This can be changed later on if we remove the DB() import
    script_dir = Path(__file__).resolve().parent
    for py_file in script_dir.rglob('*.py'):
        if py_file.name == 'base.py':
            continue

        relative_path = py_file.relative_to(script_dir).with_suffix('')
        module_path = f"optimization_providers.{'.'.join(relative_path.parts)}"

        #pylint: disable=broad-exception-caught
        try:
            importlib.import_module(module_path)
            print(f"Trying to import {module_path}")
        except Exception as e:
            print(f"Failed to import {module_path}: {e}")


    print(f"Imported {len(reporters)} optimization reporters")

    return keep_files
