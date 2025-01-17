import os
import subprocess
import hashlib
import json

from lib.db import DB
from lib.global_config import GlobalConfig
from lib import metric_importer
from metric_providers.cpu.utilization.cgroup.container.provider import CpuUtilizationCgroupContainerProvider
from metric_providers.cpu.utilization.cgroup.system.provider import CpuUtilizationCgroupSystemProvider
from metric_providers.psu.energy.ac.mcp.machine.provider import PsuEnergyAcMcpMachineProvider
from metric_providers.cpu.energy.rapl.msr.component.provider import CpuEnergyRaplMsrComponentProvider
from metric_providers.network.io.procfs.system.provider import NetworkIoProcfsSystemProvider

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

TEST_MEASUREMENT_CONTAINERS = {'bb0ea912f295ab0d8b671caf061929de9bb8b106128c071d6a196f9b6c05cd98': {'name': 'Arne'}, 'f78f0ca43069836d975f2bd4c45724227bbc71fc4788e60b33a77f1494cd2e0c': {'name': 'Not-Arne'}}
TEST_MEASUREMENT_START_TIME = 1735047190000000
TEST_MEASUREMENT_END_TIME = 1735047660000000
TEST_MEASUREMENT_DURATION = TEST_MEASUREMENT_END_TIME - TEST_MEASUREMENT_START_TIME
TEST_MEASUREMENT_DURATION_S = TEST_MEASUREMENT_DURATION / 1_000_000
TEST_MEASUREMENT_DURATION_H = TEST_MEASUREMENT_DURATION_S/60/60

def insert_run(*, uri='test-uri', branch='test-branch', filename='test-filename', user_id=1, machine_id=1):
    # spoof time from the beginning of UNIX time until now.
    phases = [
        {"start": TEST_MEASUREMENT_START_TIME-8, "name": "[BASELINE]", "end": TEST_MEASUREMENT_START_TIME-7},
        {"start": TEST_MEASUREMENT_START_TIME-6, "name": "[INSTALL]", "end": TEST_MEASUREMENT_START_TIME-5},
        {"start": TEST_MEASUREMENT_START_TIME-4, "name": "[BOOT]", "end": TEST_MEASUREMENT_START_TIME-3},
        {"start": TEST_MEASUREMENT_START_TIME-2, "name": "[IDLE]", "end": TEST_MEASUREMENT_START_TIME-1},
        {"start": TEST_MEASUREMENT_START_TIME, "name": "[RUNTIME]", "end": TEST_MEASUREMENT_END_TIME},
        {"start": TEST_MEASUREMENT_END_TIME+1, "name": "[REMOVE]", "end": TEST_MEASUREMENT_END_TIME+2},
    ]

    return DB().fetch_one('''
        INSERT INTO runs (uri, branch, filename, phases, user_id, machine_id)
        VALUES
        (%s, %s, %s, %s, %s, %s) RETURNING id;
    ''', params=(uri, branch, filename, json.dumps(phases), user_id, machine_id))[0]

def import_single_cpu_energy_measurement(run_id):

    obj = CpuEnergyRaplMsrComponentProvider(1000, skip_check=True)
    obj._filename = os.path.join(CURRENT_DIR, 'data/metrics/cpu_energy_rapl_msr_component_single_measurement.log')
    df = obj.read_metrics()

    metric_importer.import_measurements(df, 'cpu_energy_rapl_msr_component', run_id)

    return df

def import_single_network_io_procfs_measurement(run_id):

    obj = NetworkIoProcfsSystemProvider(1000, skip_check=True, remove_virtual_interfaces=False)
    obj._filename = os.path.join(CURRENT_DIR, 'data/metrics/network_io_procfs_system_single_measurement.log')
    df = obj.read_metrics()

    metric_importer.import_measurements(df, 'network_io_procfs_system', run_id)

    return df

def import_two_network_io_procfs_measurements(run_id):

    obj = NetworkIoProcfsSystemProvider(1000, skip_check=True, remove_virtual_interfaces=False)
    obj._filename = os.path.join(CURRENT_DIR, 'data/metrics/network_io_procfs_system_two_measurements.log')
    df = obj.read_metrics()

    metric_importer.import_measurements(df, 'network_io_procfs_system', run_id)

    return df

def import_cpu_utilization_container(run_id):

    obj = CpuUtilizationCgroupContainerProvider(99, skip_check=True)

    obj._filename = os.path.join(CURRENT_DIR, 'data/metrics/cpu_utilization_cgroup_container.log')

    obj.add_containers(TEST_MEASUREMENT_CONTAINERS)

    df = obj.read_metrics()

    metric_importer.import_measurements(df, 'cpu_utilization_cgroup_container', run_id)

    return df

def import_cpu_utilization_system(run_id):

    obj = CpuUtilizationCgroupSystemProvider(99, skip_check=True)

    obj._filename = os.path.join(CURRENT_DIR, 'data/metrics/cpu_utilization_cgroup_system.log')
    df = obj.read_metrics()

    metric_importer.import_measurements(df, 'cpu_utilization_cgroup_syste,', run_id)

    return df


def import_machine_energy(run_id):

    obj = PsuEnergyAcMcpMachineProvider(99, skip_check=True)

    obj._filename = os.path.join(CURRENT_DIR, 'data/metrics/psu_energy_ac_mcp_machine.log')
    df = obj.read_metrics()

    metric_importer.import_measurements(df, 'psu_energy_ac_mcp_machine', run_id)

    return df

def import_network_io_procfs(run_id):

    obj = NetworkIoProcfsSystemProvider(99, skip_check=True, remove_virtual_interfaces=False)

    obj._filename = os.path.join(CURRENT_DIR, 'data/metrics/network_io_procfs_system.log')
    df = obj.read_metrics()

    metric_importer.import_measurements(df, 'network_io_procfs_system', run_id)

    return df

def import_cpu_energy(run_id):

    obj = CpuEnergyRaplMsrComponentProvider(99, skip_check=True)

    obj._filename = os.path.join(CURRENT_DIR, 'data/metrics/cpu_energy_rapl_msr_component.log')
    df = obj.read_metrics()

    metric_importer.import_measurements(df, 'cpu_energy_rapl_msr_component', run_id)

    return df

def update_user_token(user_id, token):
    sha256_hash = hashlib.sha256()
    sha256_hash.update(token.encode('UTF-8'))

    DB().query('''
        UPDATE users
        SET token = %s
        WHERE id = %s
    ''', params=(sha256_hash.hexdigest(), user_id))


def insert_user(user_id, token):
    sha256_hash = hashlib.sha256()
    sha256_hash.update(token.encode('UTF-8'))

    # Reminder: because of f-string all {} braces are doubled to be escaped
    DB().query(f"""
        INSERT INTO "public"."users"("id", "name","token","capabilities","created_at")
        VALUES
        (%s, %s, %s,E'{{"user":{{"visible_users":[{user_id}],"is_super_user": false}},"api":{{"quotas":{{}},"routes":["/v2/carbondb/add","/v2/carbondb/filters","/v2/carbondb","/v1/carbondb/add","/v1/ci/measurement/add","/v2/ci/measurement/add","/v1/software/add","/v1/hog/add","/v1/authentication/data"]}},"data":{{"runs":{{"retention":2678400}},"hog_tasks":{{"retention":2678400}},"measurements":{{"retention":2678400}},"hog_coalitions":{{"retention":2678400}},"ci_measurements":{{"retention":2678400}},"hog_measurements":{{"retention":2678400}}}},"jobs":{{"schedule_modes":["one-off","daily","weekly","commit","variance"]}},"machines":[1],"measurement":{{"quotas":{{}},"settings":{{"total-duration":86400,"flow-process-duration":86400}}}},"optimizations":["container_memory_utilization","container_cpu_utilization","message_optimization","container_build_time","container_boot_time","container_image_size"]}}',E'2024-08-22 11:28:24.937262+00');
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
    # DB().query('DROP schema "public" CASCADE') # we do not want to call DB commands. Reason being is that because of a misconfiguration we could be sending this to the live DB
    subprocess.run(
        ['docker', 'exec', '--user', 'postgres', 'test-green-coding-postgres-container', 'bash', '-c', 'psql -d test-green-coding --port 9573 -c \'DROP schema "public" CASCADE\' '],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )
    subprocess.run(
        ['docker', 'exec', '--user', 'postgres', 'test-green-coding-postgres-container', 'bash', '-c', 'psql --port 9573 < ./docker-entrypoint-initdb.d/01-structure.sql'],
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
            self.__runner.clear_caches()
            self.__runner.check_system('start')
            self.__runner.initialize_folder(self.__runner._tmp_folder)
            self.__runner.checkout_repository()
            self.__runner.initial_parse()
            self.__runner.register_machine_id()
            self.__runner.import_metric_providers()
            if step == 'import_metric_providers':
                return
            self.__runner.populate_image_names()
            self.__runner.prepare_docker()
            self.__runner.check_running_containers()
            self.__runner.remove_docker_images()
            self.__runner.download_dependencies()
            self.__runner.initialize_run()

            self.__runner.start_metric_providers(allow_other=True, allow_container=False)
            self.__runner.custom_sleep(config['measurement']['pre-test-sleep'])

            self.__runner.start_phase('[BASELINE]')
            self.__runner.custom_sleep(config['measurement']['baseline-duration'])
            self.__runner.end_phase('[BASELINE]')

            self.__runner.start_phase('[INSTALLATION]')
            self.__runner.build_docker_images()
            self.__runner.end_phase('[INSTALLATION]')

            self.__runner.save_image_and_volume_sizes()

            self.__runner.start_phase('[BOOT]')
            self.__runner.setup_networks()
            if step == 'setup_networks':
                return
            self.__runner.setup_services()
            if step == 'setup_services':
                return
            self.__runner.end_phase('[BOOT]')

            self.__runner.add_containers_to_metric_providers()
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
            self.__runner.stop_metric_providers()
            self.__runner.read_and_cleanup_processes()
            self.__runner.save_notes_runner()
            self.__runner.save_stdout_logs()

            if self.__runner._dev_no_phase_stats is False:
                from tools.phase_stats import build_and_store_phase_stats # pylint: disable=import-outside-toplevel
                build_and_store_phase_stats(self.__runner._run_id, self.__runner._sci)

        except BaseException as exc:
            self.__runner.add_to_log(exc.__class__.__name__, str(exc))
            raise exc

    def __exit__(self, exc_type, exc_value, traceback):
        self.__runner.cleanup()
