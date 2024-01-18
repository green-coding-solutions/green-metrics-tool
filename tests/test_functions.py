import os
import re
import shutil

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from pathlib import Path

from lib.global_config import GlobalConfig
from lib import utils
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

def replace_include_in_usage_scenario(usage_scenario_path, docker_compose_filename):
    with open(usage_scenario_path, 'r', encoding='utf-8') as file:
        data = file.read()
        data = re.sub(r'docker-compose-file', docker_compose_filename, data)
    with open(usage_scenario_path, 'w', encoding='utf-8') as file:
        file.write(data)


def setup_runner(usage_scenario, docker_compose=None, uri='default', uri_type='folder', branch=None,
        debug_mode=False, allow_unsafe=False, no_file_cleanup=False,
        skip_unsafe=False, verbose_provider_boot=False, dir_name=None, dev_no_build=False, skip_system_checks=True,
        dev_no_sleeps=True, dev_no_metrics=True):
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

    RUN_NAME = 'test_' + utils.randomword(12)

    return Runner(name=RUN_NAME, uri=uri, uri_type=uri_type, filename=usage_scenario, branch=branch,
        debug_mode=debug_mode, allow_unsafe=allow_unsafe, no_file_cleanup=no_file_cleanup,
        skip_unsafe=skip_unsafe, verbose_provider_boot=verbose_provider_boot, dev_no_build=dev_no_build,
        skip_system_checks=skip_system_checks, dev_no_sleeps=dev_no_sleeps, dev_no_metrics=dev_no_metrics)

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
