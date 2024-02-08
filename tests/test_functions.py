import os
import re
import shutil
import yaml

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from pathlib import Path

from lib.global_config import GlobalConfig
from lib.yml_helpers import Loader
from lib import utils
from runner import Runner

#create test/tmp directory with specified usage_scenario to be passed as uri to runner
def make_proj_dir(dir_name, usage_scenario_path, docker_compose_path=None):
    if not os.path.exists('tmp'):
        os.mkdir('tmp')
    if not os.path.exists('tmp/' + dir_name):
        os.mkdir('tmp/' + dir_name)

    dir_path = os.path.join(CURRENT_DIR, 'tmp' ,dir_name)
    shutil.copy2(usage_scenario_path, dir_path)
    # copy over compose.yml and Dockerfile (from stress for now)
    if docker_compose_path is not None:
        shutil.copy2(docker_compose_path, os.path.join(CURRENT_DIR, 'tmp' ,dir_name))
        dockerfile = os.path.join(CURRENT_DIR, 'stress-application/Dockerfile')
        shutil.copy2(dockerfile, os.path.join(CURRENT_DIR, 'tmp' ,dir_name))
    return dir_path

def replace_include_in_usage_scenario(usage_scenario_path, docker_compose_filename):
    with open(usage_scenario_path, 'r', encoding='utf-8') as file:
        data = file.read()
        data = re.sub(r'docker-compose-file', docker_compose_filename, data)
    with open(usage_scenario_path, 'w', encoding='utf-8') as file:
        file.write(data)

def parallelize_runner_folders(runner, parallel_id):
    runner._tmp_folder = f"/tmp/gmt_tests_{parallel_id}/green-metrics-tool/"
    runner._folder = f"{runner._tmp_folder}/repo"

def edit_yml_with_id(yml_path, parallel_id):
    with open(yml_path, 'r', encoding='utf-8') as fp:
        yml_data = yaml.load(fp, Loader=Loader)

        # Update services
        services_copy = dict(yml_data.get('services', {}))
        for service_name, service_info in services_copy.items():
            new_service_name = f"{service_name}_{parallel_id}"
            yml_data['services'][new_service_name] = service_info
            del yml_data['services'][service_name]

            # Update networks within service
            service_networks = service_info.get('networks')
            if service_networks:
                if isinstance(service_networks, list):
                    service_info['networks'] = [f"{network}_{parallel_id}" for network in service_networks]
                elif isinstance(service_networks, dict):
                    service_info['networks'] = {f"{key}_{parallel_id}": value for key, value in service_networks.items()}

            if 'container_name' in service_info:
                service_info['container_name'] = f"{service_info['container_name']}_{parallel_id}"

            if 'depends_on' in service_info:
                service_info['depends_on'] = [f"{dep}_{parallel_id}" for dep in service_info['depends_on']]

        # top level networks
        networks = yml_data.get('networks')
        if networks:
            if isinstance(networks, list):
                yml_data['networks'] = [f"{network}_{parallel_id}" for network in networks]
            elif isinstance(networks, dict):
                yml_data['networks'] = {f"{key}_{parallel_id}": value for key, value in networks.items()}

        # Update container names in the flow section
        for item in yml_data.get('flow', []):
            if 'container' in item:
                item['container'] = f"{item['container']}_{parallel_id}"

    # Save the updated YAML file
    with open(yml_path, 'w', encoding='utf-8') as fp:
        yaml.dump(yml_data, fp, sort_keys=False) #sort_keys=False preserves the original order

def parallelize_files(proj_dir, usage_scenario_file, docker_compose='compose.yml', parallel_id=None):
    if parallel_id is None:
        parallel_id = utils.randomword(12)
    if docker_compose is None:
        docker_compose = 'compose.yml'
    usage_scenario_path = os.path.join(proj_dir, usage_scenario_file)
    docker_compose_path = os.path.join(proj_dir, docker_compose)

    # need to do docker compose first, in case its loaded by the usage_scenario
    edit_yml_with_id(docker_compose_path, parallel_id)
    edit_yml_with_id(usage_scenario_path, parallel_id)


def setup_runner(name=None, usage_scenario="usage_scenario.yml", docker_compose=None, uri='default',
        uri_type='folder', branch=None, debug_mode=False, allow_unsafe=False, no_file_cleanup=False,
        skip_unsafe=False, verbose_provider_boot=False, dir_name=None, dev_no_build=False, skip_system_checks=True,
        dev_no_sleeps=True, dev_no_metrics=True, parallel_id=None, create_tmp_directory=True, do_parallelize_files=True):

    if parallel_id is None:
        parallel_id = utils.randomword(12)

    # parallelization of files only for uri_type folders, so far
    # because url type means we are checking out a repo, and that happens already too late
    if uri_type == 'folder':
        if dir_name is None:
            dir_name = parallel_id

        if create_tmp_directory:
            if docker_compose is not None:
                docker_compose_path = os.path.join(CURRENT_DIR, 'data/docker-compose-files/', docker_compose)
            else:
                docker_compose_path = os.path.join(CURRENT_DIR, 'data/docker-compose-files/compose.yml')
            usage_scenario_path = os.path.join(CURRENT_DIR, 'data/usage_scenarios/', usage_scenario)
            make_proj_dir(dir_name=dir_name, usage_scenario_path=usage_scenario_path, docker_compose_path=docker_compose_path)

        uri = os.path.join(CURRENT_DIR, 'tmp/', dir_name)
        if do_parallelize_files:
            parallelize_files(uri, usage_scenario, docker_compose, parallel_id)
    elif uri_type == 'URL':
        if uri[0:8] != 'https://' and uri[0:7] != 'http://':
            raise ValueError("Invalid uri for URL")
    else:
        raise ValueError("Invalid uri_type")

    if name is None:
        name = f'test_{parallel_id}'

    runner = Runner(name=name, uri=uri, uri_type=uri_type, filename=usage_scenario, branch=branch,
        debug_mode=debug_mode, allow_unsafe=allow_unsafe, no_file_cleanup=no_file_cleanup,
        skip_unsafe=skip_unsafe, verbose_provider_boot=verbose_provider_boot, dev_no_build=dev_no_build,
        skip_system_checks=skip_system_checks, dev_no_sleeps=dev_no_sleeps, dev_no_metrics=dev_no_metrics)

    parallelize_runner_folders(runner, parallel_id)

    return runner


# This function runs the runner up to and *including* the specified step
# remember to catch in try:finally and do cleanup when calling this!
#pylint: disable=redefined-argument-from-local
def run_until(runner, step):
    try:
        config = GlobalConfig().config
        runner.check_system('start')
        runner.initialize_folder(runner._tmp_folder)
        runner.checkout_repository()
        runner.initialize_run()
        runner.initial_parse()
        if step == 'import_metric_providers':
            return
        runner.import_metric_providers()
        runner.populate_image_names()
        runner.prepare_docker()
        runner.check_running_containers()
        runner.remove_docker_images()
        runner.download_dependencies()
        runner.register_machine_id()
        runner.update_and_insert_specs()

        runner.start_metric_providers(allow_other=True, allow_container=False)
        runner.custom_sleep(config['measurement']['idle-time-start'])

        runner.start_measurement()

        runner.start_phase('[BASELINE]')
        runner.custom_sleep(5)
        runner.end_phase('[BASELINE]')

        runner.start_phase('[INSTALLATION]')
        runner.build_docker_images()
        runner.end_phase('[INSTALLATION]')

        runner.start_phase('[BOOT]')
        runner.setup_networks()
        if step == 'setup_networks':
            return
        runner.setup_services()
        if step == 'setup_services':
            return
        runner.end_phase('[BOOT]')

        runner.start_metric_providers(allow_container=True, allow_other=False)

        runner.start_phase('[IDLE]')
        runner.custom_sleep(5)
        runner.end_phase('[IDLE]')

        runner.start_phase('[RUNTIME]')
        runner.run_flows() # can trigger debug breakpoints;
        runner.end_phase('[RUNTIME]')

        runner.start_phase('[REMOVE]')
        runner.custom_sleep(1)
        runner.end_phase('[REMOVE]')

        runner.end_measurement()
        runner.check_process_returncodes()
        runner.custom_sleep(config['measurement']['idle-time-end'])
        runner.store_phases()
        runner.update_start_and_end_times()
        runner.read_and_cleanup_processes()
    except BaseException as exc:
        runner.add_to_log(exc.__class__.__name__, str(exc))
        raise exc

def cleanup(runner):
    try:
        runner.read_container_logs()
    except BaseException as exc:
        runner.add_to_log(exc.__class__.__name__, str(exc))
        raise exc
    finally:
        try:
            runner.read_and_cleanup_processes()
        except BaseException as exc:
            runner.add_to_log(exc.__class__.__name__, str(exc))
            raise exc
        finally:
            try:
                runner.save_notes_runner()
            except BaseException as exc:
                runner.add_to_log(exc.__class__.__name__, str(exc))
                raise exc
            finally:
                try:
                    runner.stop_metric_providers()
                except BaseException as exc:
                    runner.add_to_log(exc.__class__.__name__, str(exc))
                    raise exc
                finally:
                    try:
                        runner.save_stdout_logs()
                    except BaseException as exc:
                        runner.add_to_log(exc.__class__.__name__, str(exc))
                        raise exc
                    finally:
                        runner.cleanup()  # always run cleanup automatically after each run

def assertion_info(expected, actual):
    return f"Expected: {expected}, Actual: {actual}"

def create_test_file(path):
    if not os.path.exists(path):
        os.mkdir(path)
    Path(f"{path}/test-file").touch()

# test this file
if __name__ == '__main__':
    setup_runner('import_error.yml', parallel_id=123)
