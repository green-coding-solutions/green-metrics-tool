import os
import subprocess

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from pathlib import Path

from lib.global_config import GlobalConfig
from lib import utils

def assertion_info(expected, actual):
    return f"Expected: {expected}, Actual: {actual}"

def create_test_file(path):
    if not os.path.exists(path):
        os.mkdir(path)
    Path(f"{path}/test-file").touch()

def create_tmp_dir():
    tmp_dir_name = utils.randomword(12)
    if not os.path.exists(os.path.join(CURRENT_DIR, 'tmp/')):
        os.mkdir(os.path.join(CURRENT_DIR, 'tmp/'))
    os.mkdir('tmp/' + tmp_dir_name)
    tmp_dir = os.path.join(CURRENT_DIR, f'tmp/{tmp_dir_name}')
    return tmp_dir, tmp_dir_name

def check_if_container_running(container_name):
    ps = subprocess.run(
            ['docker', 'container', 'inspect', '-f', '{{.State.Running}}', container_name],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8',
            check=False,
        )
    if ps.returncode != 0:
        return False
    return True

class RunUntilManager:
    def __init__(self, runner):
        self.__runner = runner

    def __enter__(self):
        return self

    def run_until(self, step):
        try:
            config = GlobalConfig().config
            self.__runner.check_system('start')
            self.__runner.initialize_folder(self.__runner._tmp_folder)
            self.__runner.checkout_repository()
            self.__runner.initialize_run()
            self.__runner.initial_parse()
            self.__runner.import_metric_providers()
            if step == 'import_metric_providers':
                return
            self.__runner.populate_image_names()
            self.__runner.prepare_docker()
            self.__runner.check_running_containers()
            self.__runner.remove_docker_images()
            self.__runner.download_dependencies()
            self.__runner.register_machine_id()
            self.__runner.update_and_insert_specs()

            self.__runner.start_metric_providers(allow_other=True, allow_container=False)
            self.__runner.custom_sleep(config['measurement']['idle-time-start'])

            self.__runner.start_measurement()

            self.__runner.start_phase('[BASELINE]')
            self.__runner.custom_sleep(5)
            self.__runner.end_phase('[BASELINE]')

            self.__runner.start_phase('[INSTALLATION]')
            self.__runner.build_docker_images()
            self.__runner.end_phase('[INSTALLATION]')

            self.__runner.start_phase('[BOOT]')
            self.__runner.setup_networks()
            if step == 'setup_networks':
                return
            self.__runner.setup_services()
            if step == 'setup_services':
                return
            self.__runner.end_phase('[BOOT]')

            self.__runner.start_metric_providers(allow_container=True, allow_other=False)

            self.__runner.start_phase('[IDLE]')
            self.__runner.custom_sleep(5)
            self.__runner.end_phase('[IDLE]')

            self.__runner.start_phase('[RUNTIME]')
            self.__runner.run_flows() # can trigger debug breakpoints;
            self.__runner.end_phase('[RUNTIME]')

            self.__runner.start_phase('[REMOVE]')
            self.__runner.custom_sleep(1)
            self.__runner.end_phase('[REMOVE]')

            self.__runner.end_measurement()
            self.__runner.check_process_returncodes()
            self.__runner.custom_sleep(config['measurement']['idle-time-end'])
            self.__runner.store_phases()
            self.__runner.update_start_and_end_times()
            self.__runner.read_and_cleanup_processes()
        except BaseException as exc:
            self.__runner.add_to_log(exc.__class__.__name__, str(exc))
            raise exc

    def __exit__(self, exc_type, exc_value, traceback):
        self.__runner.cleanup()
