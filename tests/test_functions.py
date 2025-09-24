import os
import subprocess
import hashlib
import json

from lib.db import DB
from lib.global_config import GlobalConfig
from lib.log_types import LogType
from lib import metric_importer
from metric_providers.cpu.utilization.cgroup.container.provider import CpuUtilizationCgroupContainerProvider
from metric_providers.cpu.utilization.cgroup.system.provider import CpuUtilizationCgroupSystemProvider
from metric_providers.psu.energy.ac.mcp.machine.provider import PsuEnergyAcMcpMachineProvider
from metric_providers.cpu.energy.rapl.msr.component.provider import CpuEnergyRaplMsrComponentProvider
from metric_providers.network.io.procfs.system.provider import NetworkIoProcfsSystemProvider
from metric_providers.network.io.cgroup.container.provider import NetworkIoCgroupContainerProvider

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

TEST_MEASUREMENT_CONTAINERS = {'bb0ea912f295ab0d8b671caf061929de9bb8b106128c071d6a196f9b6c05cd98': {'name': 'Arne'}, 'f78f0ca43069836d975f2bd4c45724227bbc71fc4788e60b33a77f1494cd2e0c': {'name': 'Not-Arne'}}
TEST_MEASUREMENT_START_TIME = 1735047190000000
TEST_MEASUREMENT_END_TIME = 1735047660000000
TEST_MEASUREMENT_DURATION = TEST_MEASUREMENT_END_TIME - TEST_MEASUREMENT_START_TIME
TEST_MEASUREMENT_DURATION_S = TEST_MEASUREMENT_DURATION / 1_000_000
TEST_MEASUREMENT_DURATION_H = TEST_MEASUREMENT_DURATION_S/60/60

def shorten_sleep_times(duration_in_s):
    DB().query("UPDATE users SET capabilities = jsonb_set(capabilities,'{measurement,pre_test_sleep}',%s,false)", params=(str(duration_in_s), ))
    DB().query("UPDATE users SET capabilities = jsonb_set(capabilities,'{measurement,baseline_duration}',%s,false)", params=(str(duration_in_s), ))
    DB().query("UPDATE users SET capabilities = jsonb_set(capabilities,'{measurement,idle_duration}',%s,false)", params=(str(duration_in_s), ))
    DB().query("UPDATE users SET capabilities = jsonb_set(capabilities,'{measurement,post_test_sleep}',%s,false)", params=(str(duration_in_s), ))
    DB().query("UPDATE users SET capabilities = jsonb_set(capabilities,'{measurement,phase_transition_time}',%s,false)", params=(str(duration_in_s), ))


def insert_run(*, uri='test-uri', branch='test-branch', filename='test-filename', user_id=1, machine_id=1):
    # spoof time from the beginning of UNIX time until now.
    phases = [
        {"start": TEST_MEASUREMENT_START_TIME-8, "name": "[BASELINE]", "end": TEST_MEASUREMENT_START_TIME-7},
        {"start": TEST_MEASUREMENT_START_TIME-6, "name": "[INSTALL]", "end": TEST_MEASUREMENT_START_TIME-5},
        {"start": TEST_MEASUREMENT_START_TIME-4, "name": "[BOOT]", "end": TEST_MEASUREMENT_START_TIME-3},
        {"start": TEST_MEASUREMENT_START_TIME-2, "name": "[IDLE]", "end": TEST_MEASUREMENT_START_TIME-1},
        {"start": TEST_MEASUREMENT_START_TIME, "name": "[RUNTIME]", "end": TEST_MEASUREMENT_END_TIME},
        {"start": TEST_MEASUREMENT_START_TIME, "name": "Only Phase", "end": TEST_MEASUREMENT_END_TIME},
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

def import_two_network_io_procfs_measurements_at_phase_border(run_id):

    obj = NetworkIoProcfsSystemProvider(1000, skip_check=True, remove_virtual_interfaces=False)
    obj._filename = os.path.join(CURRENT_DIR, 'data/metrics/network_io_procfs_system_two_measurements_at_phase_border.log')
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

    metric_importer.import_measurements(df, 'cpu_utilization_cgroup_system,', run_id)

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

def import_network_io_cgroup_container(run_id):

    obj = NetworkIoCgroupContainerProvider(99, skip_check=True)

    obj._filename = os.path.join(CURRENT_DIR, 'data/metrics/network_io_cgroup_container.log')
    df = obj.read_metrics()

    metric_importer.import_measurements(df, 'network_io_cgroup_container', run_id)

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

    DB().query("""
        INSERT INTO "public"."users"("id", "name","token","capabilities","created_at")
        VALUES
        (%s, %s, %s, (SELECT capabilities FROM users WHERE id = 1), E'2024-08-22 11:28:24.937262+00')
    """, params=(user_id, token, sha256_hash.hexdigest()))
    DB().query("""
        UPDATE users SET capabilities = jsonb_set(capabilities, '{user,visible_users}', %s ,false)
            WHERE id = %s
    """, params=(str(user_id), user_id))


def import_demo_data():
    config = GlobalConfig().config
    pg_port = config['postgresql']['port']
    pg_dbname = config['postgresql']['dbname']
    ps = subprocess.run(
        f"docker exec -i --user postgres test-green-coding-postgres-container psql -d{pg_dbname} -p{pg_port} < {CURRENT_DIR}/../data/demo_data.sql",
        check=True,
        shell=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    if ps.stderr != '':
        reset_db()
        raise RuntimeError('Import of Demo data into DB failed', ps.stderr)

def import_demo_data_ee():
    config = GlobalConfig().config
    pg_port = config['postgresql']['port']
    pg_dbname = config['postgresql']['dbname']
    ps = subprocess.run(
        f"docker exec -i --user postgres test-green-coding-postgres-container psql -d{pg_dbname} -p{pg_port} < {CURRENT_DIR}/../ee/data/demo_data_ee.sql",
        check=True,
        shell=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    if ps.stderr != '':
        reset_db()
        raise RuntimeError('Import of Demo data into DB failed', ps.stderr)

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
    subprocess.run([
        'docker', 'compose', '-f', f"{CURRENT_DIR}/data/stress-application/compose.yml", 'build',
        '--build-arg', f'HTTP_PROXY={os.environ.get("HTTP_PROXY")}',
        '--build-arg', f'HTTPS_PROXY={os.environ.get("HTTPS_PROXY")}',
        '--build-arg', f'NO_PROXY={os.environ.get("NO_PROXY")}',
        '--build-arg', f'http_proxy={os.environ.get("http_proxy")}',
        '--build-arg', f'https_proxy={os.environ.get("https_proxy")}',
        '--build-arg', f'no_proxy={os.environ.get("no_proxy")}',
    ], check=True)

# should be preceded by a yield statement and on autouse
def reset_db():
    # DB().query('DROP schema "public" CASCADE') # we do not want to call DB commands. Reason being is that because of a misconfiguration we could be sending this to the live DB
    config = GlobalConfig().config
    pg_port = config['postgresql']['port']
    pg_dbname = config['postgresql']['dbname']
    redis_port = config['redis']['port']
    subprocess.run(
        ['docker', 'exec', '--user', 'postgres', 'test-green-coding-postgres-container', 'bash', '-c', f'psql -d {pg_dbname} --port {pg_port} -c \'DROP SCHEMA IF EXISTS "public" CASCADE\' '],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ['docker', 'exec', '--user', 'postgres', 'test-green-coding-postgres-container', 'bash', '-c', f'psql -d {pg_dbname} --port {pg_port} < ./docker-entrypoint-initdb.d/01-structure.sql'],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    subprocess.run(
        ['docker', 'exec', 'test-green-coding-redis-container', 'redis-cli', '-p', f"{redis_port}", 'FLUSHALL'],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

class RunUntilManager:
    def __init__(self, runner):
        self._active = False
        self.__runner = runner

    def __enter__(self):
        self._active = True
        return self

    def run_until(self, step):
        """
        Execute the runner pipeline until the specified step.
            
        Note:
            This is a convenience wrapper around run_steps(stop_at=step).
            For more control and inspection capabilities, use run_steps() directly.
        """
        for _ in self.run_steps(stop_at=step):
            pass

    def run_steps(self, stop_at=None):
        """
        Generator that executes the runner pipeline, yielding at predefined pause points.        
        
        Example:
            # Run with inspection at all pause points:
            with RunUntilManager(runner) as context:
                for pause_point in context.run_steps():
                    print(f"Reached pause point: {pause_point}")

            # Run until specific pause point (with inspection at all pause points along the way):
            with RunUntilManager(runner) as context:
                for pause_point in context.run_steps(stop_at='initialize_run'):
                    print(f"Reached pause point: {pause_point}")
                    # This will print both 'import_metric_providers' and 'initialize_run'
        """
        if not getattr(self, '_active', False):
            raise RuntimeError("run_steps must be used within the context")

        try:
            self.__runner._start_measurement()
            self.__runner._clear_caches()
            self.__runner._check_system('start')
            self.__runner._initialize_folder(self.__runner._tmp_folder)
            self.__runner._checkout_repository()
            self.__runner._load_yml_file()
            self.__runner._initial_parse()
            self.__runner._register_machine_id()
            self.__runner._import_metric_providers()
            yield 'import_metric_providers'
            if stop_at == 'import_metric_providers':
                return
            self.__runner._populate_image_names()
            self.__runner._prepare_docker()
            self.__runner._check_running_containers_before_start()
            self.__runner._remove_docker_images()
            self.__runner._download_dependencies()
            self.__runner._initialize_run()
            yield 'initialize_run'
            if stop_at == 'initialize_run':
                return
            self.__runner._start_metric_providers(allow_other=True, allow_container=False)
            self.__runner._custom_sleep(self.__runner._measurement_pre_test_sleep)

            self.__runner._start_phase('[BASELINE]')
            self.__runner._custom_sleep(self.__runner._measurement_baseline_duration)
            self.__runner._end_phase('[BASELINE]')

            self.__runner._start_phase('[INSTALLATION]')
            self.__runner._build_docker_images()
            self.__runner._end_phase('[INSTALLATION]')

            self.__runner._save_image_and_volume_sizes()
            yield 'save_image_and_volume_sizes'
            if stop_at == 'save_image_and_volume_sizes':
                return
            self.__runner._start_phase('[BOOT]')
            self.__runner._setup_networks()
            yield 'setup_networks'
            if stop_at == 'setup_networks':
                return
            self.__runner._setup_services()
            yield 'setup_services'
            if stop_at == 'setup_services':
                return
            self.__runner._end_phase('[BOOT]')

            self.__runner._check_running_containers_after_boot_phase()
            self.__runner._check_process_returncodes()

            self.__runner._add_containers_to_metric_providers()
            self.__runner._start_metric_providers(allow_container=True, allow_other=False)

            self.__runner._collect_container_dependencies()
            if stop_at == 'collect_container_dependencies':
                return

            self.__runner._start_phase('[IDLE]')
            self.__runner._custom_sleep(self.__runner._measurement_idle_duration)
            self.__runner._end_phase('[IDLE]')

            self.__runner._start_phase('[RUNTIME]')
            self.__runner._run_flows() # can trigger debug breakpoints;
            self.__runner._end_phase('[RUNTIME]')
            yield 'runtime_complete'
            if stop_at == 'runtime_complete':
                return

            self.__runner._check_running_containers_after_runtime_phase()

            self.__runner._start_phase('[REMOVE]')
            self.__runner._custom_sleep(1)
            self.__runner._end_phase('[REMOVE]')

            self.__runner._end_measurement()
            self.__runner._check_process_returncodes()
            self.__runner._check_system('end')
            self.__runner._custom_sleep(self.__runner._measurement_post_test_sleep)
            self.__runner._identify_invalid_run()
            self.__runner._post_process(0)

        except BaseException as exc:
            self.__runner._add_to_current_run_log(
                container_name="[SYSTEM]",
                log_type=LogType.EXCEPTION,
                log_id=id(exc),
                cmd="run_test",
                phase=None,
                stderr=str(exc),
                exception_class=exc.__class__.__name__
            )
            raise exc

    def __exit__(self, exc_type, exc_value, traceback):
        self._active = False
        self.__runner.cleanup()
