from optimization_providers.base import Criticality, register_reporter
from lib import error_helpers
import subprocess

REPORTER_NAME = 'images'
REPORTER_ICON = 'todo'

MAX_INSTALL_DURATION = 300 # 5 Minutes
MAX_BOOT_DURATION = 5 # 5 seconds

# pylint: disable=unused-argument
@register_reporter('image-size', Criticality.INFO, REPORTER_NAME, REPORTER_ICON, req_providers =[])
def container_image_size(self, run, measurements, repo_path, network, notes, phases):

    # print("run is", run)

    image_size = subprocess.run(
                    [
                        'docker',
                        'images',
                        '--format', '"{{.Size}}"'
                    ],
                    check=True,
                    capture_output=True,
                    encoding='UTF-8',
                )
