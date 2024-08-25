from optimization_providers.base import Criticality, register_reporter
from lib import error_helpers

REPORTER_NAME = 'container-timings'
REPORTER_ICON = 'clock'

MAX_INSTALL_DURATION = 300 # 5 Minutes
MAX_BOOT_DURATION = 5 # 5 seconds

# pylint: disable=unused-argument
@register_reporter('container_build_time', Criticality.INFO, REPORTER_NAME, REPORTER_ICON, req_providers =[])
def container_build_time(self, run, measurements, repo_path, network, notes, phases):

    installation_phase = run['phases'][1]
    if installation_phase['name'] != '[INSTALLATION]':
        error_helpers.log_error('Phase mapping in optimizations was not as expected', phases=run['phases'], run_id=run['id'])
        raise RuntimeError('Phase mapping in optimizations was not as expected')

    duration = (installation_phase['end'] - installation_phase['start'])/1_000_000 # time is in microseconds

    if duration > MAX_INSTALL_DURATION:
        self.add_optimization(
            f"Container build duration too long (> {MAX_INSTALL_DURATION} s)",
            f"The build duration was {duration} s. In cases where you build the container only once a month this build time might be acceptable. For daily or even intra-daily builds try reducing this time through layer caching, multi-stage builds or using different build agents"
        )

# pylint: disable=unused-argument
@register_reporter('container_boot_time', Criticality.INFO, REPORTER_NAME, REPORTER_ICON, req_providers =[])
def container_boot_time(self, run, measurements, repo_path, network, notes, phases):

    boot_phase = run['phases'][2]
    if boot_phase['name'] != '[BOOT]':
        error_helpers.log_error('Phase mapping in optimizations was not as expected', phases=run['phases'], run_id=run['id'])
        raise RuntimeError('Phase mapping in optimizations was not as expected')

    duration = (boot_phase['end'] - boot_phase['start'])/1_000_000 # time is in microseconds

    if duration > MAX_BOOT_DURATION:
        self.add_optimization(
            f"Container boot duration too long (> {MAX_BOOT_DURATION} s)",
            f"The boot duration was {duration} s. Docker containers are supposed to be instantiated in a very short time. Try to move startup processing to the lesser executed build phase"
        )
