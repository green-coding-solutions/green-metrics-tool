from optimization_providers.base import Criticality, register_reporter

REPORTER_NAME = 'container-timings'
REPORTER_ICON = 'clock'

MAX_INSTALL_DURATION = 300 # 5 Minutes
MAX_BOOT_DURATION = 5 # 5 seconds

# pylint: disable=unused-argument
@register_reporter('container-build-time', Criticality.INFO, REPORTER_NAME, REPORTER_ICON, req_providers =[])
def container_build_time(self, run, measurements, repo_path, network, notes, phases):

    if len(run['phases']) < 2 or run['phases'][1] != '[INSTALLATION]':
        self.add_optimization(
            'Container build duration could not be analyzed',
            'INSTALLATION phase was not present'
        )
        return
    installation_phase = run['phases'][1]

    duration = (installation_phase['end'] - installation_phase['start'])/1_000_000 # time is in microseconds

    if duration > MAX_INSTALL_DURATION:
        self.add_optimization(
            f"Container build duration too long (> {MAX_INSTALL_DURATION} s)",
            f"The build duration was {duration} s. In cases where you build the container only once a month this build time might be acceptable. For daily or even intra-daily builds try reducing this time through layer caching, multi-stage builds or using different build agents"
        )

# pylint: disable=unused-argument
@register_reporter('container-boot-time', Criticality.INFO, REPORTER_NAME, REPORTER_ICON, req_providers =[])
def container_boot_time(self, run, measurements, repo_path, network, notes, phases):

    if len(run['phases']) < 3 or run['phases'][2] != '[BOOT]':
        self.add_optimization(
            'Container boot duration could not be analyzed',
            'BOOT phase was not present'
        )
        return
    boot_phase = run['phases'][2]

    duration = (boot_phase['end'] - boot_phase['start'])/1_000_000 # time is in microseconds

    if duration > MAX_BOOT_DURATION:
        self.add_optimization(
            f"Container boot duration too long (> {MAX_BOOT_DURATION} s)",
            f"The boot duration was {duration} s. Docker containers are supposed to be instantiated in a very short time. Try to move startup processing to the lesser executed build phase"
        )
