#pylint: disable=wrong-import-position
import os
import re
import shutil
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{CURRENT_DIR}/../.")
sys.path.append(f"{CURRENT_DIR}/../lib")

from pathlib import Path
from db import DB
import utils

#pylint:disable=import-error
from runner import Runner

#create test/tmp directory with specified usage_scenario to be passed as uri to runner
def make_proj_dir(dir_name, usage_scenario_path, docker_compose_path=None):
    if not os.path.exists('tmp'):
        os.mkdir('tmp')
    if not os.path.exists('tmp/' + dir_name):
        os.mkdir('tmp/' + dir_name)

    shutil.copy2(usage_scenario_path, os.path.join(CURRENT_DIR, 'tmp' ,dir_name))
    # copy over compose.yml and Dockerfile (from stress for now)
    if docker_compose_path is not None:
        shutil.copy2(docker_compose_path, os.path.join(CURRENT_DIR, 'tmp' ,dir_name))
        dockerfile = os.path.join(CURRENT_DIR, 'stress-application/Dockerfile')
        shutil.copy2(dockerfile, os.path.join(CURRENT_DIR, 'tmp' ,dir_name))
    return dir_name


def insert_project(uri):
    project_name = 'test_' + utils.randomword(12)
    pid = DB().fetch_one('INSERT INTO "projects" ("name","uri","email","last_run","created_at") \
                    VALUES \
                    (%s,%s,\'manual\',NULL,NOW()) RETURNING id;', params=(project_name, uri))[0]
    return pid

def replace_include_in_usage_scenario(usage_scenario_path, docker_compose_filename):
    with open(usage_scenario_path, 'r', encoding='utf-8') as file:
        data = file.read()
        data = re.sub(r'docker-compose-file', docker_compose_filename, data)
    with open(usage_scenario_path, 'w', encoding='utf-8') as file:
        file.write(data)


#pylint: disable=too-many-arguments
def setup_runner(usage_scenario, docker_compose=None, uri='default', uri_type='folder', branch=None,
        debug_mode=False, allow_unsafe=False, no_file_cleanup=False,
        skip_unsafe=False, verbose_provider_boot=False, dir_name=None):
    usage_scenario_path = os.path.join(CURRENT_DIR, 'data/usage_scenarios/', usage_scenario)
    if docker_compose is not None:
        docker_compose_path = os.path.join(CURRENT_DIR, 'data/docker-compose-files/', docker_compose)
    else:
        docker_compose_path = os.path.join(CURRENT_DIR, 'data/docker-compose-files/compose.yml')

    if uri == 'default':
        if dir_name is None:
            dir_name = utils.randomword(12)
        make_proj_dir(dir_name=dir_name, usage_scenario_path=usage_scenario_path, docker_compose_path=docker_compose_path)
        uri = os.path.join(CURRENT_DIR, 'tmp/', dir_name)

    pid = insert_project(uri)
    return Runner(uri=uri, uri_type=uri_type, pid=pid, filename=usage_scenario, branch=branch,
        debug_mode=debug_mode, allow_unsafe=allow_unsafe, no_file_cleanup=no_file_cleanup,
        skip_unsafe=skip_unsafe, verbose_provider_boot=verbose_provider_boot)

RUNNER_STEPS = ['prepare_filesystem_location',
                'checkout_repository',
                'initial_parse',
                'update_and_insert_specs',
                'import_metric_providers',
                'setup_networks',
                'setup_services',
                'start_metric_providers',
                'pre_idle_containers',
                'start_measurement',
                'run_flows',
                'update_start_and_end_times',
                ]
# This function runs the runner up to and *including* the specified step
#pylint: disable=redefined-argument-from-local
def run_until(runner, step):
    for step in RUNNER_STEPS:
        getattr(runner, step)()

def assertion_info(expected, actual):
    return f"Expected: {expected}, Actual: {actual}"

def create_test_file(path):
    if not os.path.exists(path):
        os.mkdir(path)
    Path(f"{path}/test-file").touch()
