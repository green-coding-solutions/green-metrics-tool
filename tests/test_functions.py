import os
import subprocess
import hashlib

from lib.db import DB

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.global_config import GlobalConfig

def insert_user(user_id, token):
    sha256_hash = hashlib.sha256()
    sha256_hash.update(token.encode('UTF-8'))

    DB().query("""
        INSERT INTO "public"."users"("id", "name","token","capabilities","created_at")
        VALUES
        (%s, %s, %s,E'{"api":{"quotas":{},"routes":["/v2/carbondb/add","/v2/carbondb/filters","/v2/carbondb","/v1/carbondb/add","/v1/ci/measurement/add","/v2/ci/measurement/add","/v1/software/add","/v1/hog/add","/v1/authentication/data"]},"data":{"runs":{"retention":2678400},"hog_tasks":{"retention":2678400},"measurements":{"retention":2678400},"hog_coalitions":{"retention":2678400},"ci_measurements":{"retention":2678400},"hog_measurements":{"retention":2678400}},"jobs":{"schedule_modes":["one-off","daily","weekly","commit","variance"]},"machines":[1],"measurement":{"quotas":{},"settings":{"total-duration":86400,"flow-process-duration":86400}},"optimizations":["container_memory_utilization","container_cpu_utilization","message_optimization","container_build_time","container_boot_time","container_image_size"]}',E'2024-08-22 11:28:24.937262+00');
    """, params=(user_id, token, sha256_hash.hexdigest()))

def import_demo_data():
    subprocess.run(
        f"docker exec -i --user postgres test-green-coding-postgres-container psql -dtest-green-coding -p9573 < {CURRENT_DIR}/../data/demo_data.sql",
        check=True,
        shell=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )


def assertion_info(expected, actual):
    return f"Expected: {expected}, Actual: {actual}"

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

def build_image_fixture():
    subprocess.run(['docker', 'compose', '-f', f"{CURRENT_DIR}/data/stress-application/compose.yml", 'build'], check=True)

# should be preceded by a yield statement and on autouse
def reset_db():
    DB().query('DROP schema "public" CASCADE')
    subprocess.run(
        ['docker', 'exec', '--user', 'postgres', 'test-green-coding-postgres-container', 'bash', '-c', 'psql --port 9573 < ./docker-entrypoint-initdb.d/structure.sql'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

class RunUntilManager:
    def __init__(self, runner):
        self.__runner = runner

    def __enter__(self):
        return self

    def run_until(self, step):
        try:
            config = GlobalConfig().config
            self.__runner.start_measurement()
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
            self.__runner.custom_sleep(config['measurement']['pre-test-sleep'])

            self.__runner.start_phase('[BASELINE]')
            self.__runner.custom_sleep(config['measurement']['baseline-duration'])
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
            self.__runner.custom_sleep(config['measurement']['idle-duration'])
            self.__runner.end_phase('[IDLE]')

            self.__runner.start_phase('[RUNTIME]')
            self.__runner.run_flows() # can trigger debug breakpoints;
            self.__runner.end_phase('[RUNTIME]')

            self.__runner.start_phase('[REMOVE]')
            self.__runner.custom_sleep(1)
            self.__runner.end_phase('[REMOVE]')

            self.__runner.end_measurement()
            self.__runner.check_process_returncodes()
            self.__runner.custom_sleep(config['measurement']['post-test-sleep'])
            self.__runner.update_start_and_end_times()
            self.__runner.store_phases()
            self.__runner.read_container_logs()
            self.__runner.read_and_cleanup_processes()
            self.__runner.save_notes_runner()
            self.__runner.stop_metric_providers()
            self.__runner.save_stdout_logs()

            if self.__runner._dev_no_phase_stats is False:
                from tools.phase_stats import build_and_store_phase_stats # pylint: disable=import-outside-toplevel
                build_and_store_phase_stats(self.__runner._run_id, self.__runner._sci)

        except BaseException as exc:
            self.__runner.add_to_log(exc.__class__.__name__, str(exc))
            raise exc

    def __exit__(self, exc_type, exc_value, traceback):
        self.__runner.cleanup()
