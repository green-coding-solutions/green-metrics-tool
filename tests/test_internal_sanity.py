# https://docs.docker.com/engine/reference/commandline/port/
# List port mappings or a specific mapping for the container
#  docker port CONTAINER [PRIVATE_PORT[/PROTO]]

import os
import subprocess

GMT_DIR = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../'))

## Note:
# This test file checks internal sanity
# Some tests files need to have a specific format and it is very easy to shoot yourself in the foot and not
# understand where the error is coming from. This these tests check if adding new tests is according to format


# All demo data we have is in GMT
# Thus also the test server must run im GMT mode to not get confusing errors
def test_check_all_demo_data_timezones_gmt():
    ps = subprocess.run(
        ['grep', '-RE', '\\+[0-9][1-9]:[0-9]{2}'],
        check=False,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )
    assert ps.returncode == 1, print('Found GMT timestamps')

def test_check_containers_running_in_GMT():
    subprocess.check_output(['grep', 'TZ=GMT', '../docker/test-compose.yml'], encoding='UTF-8')
    subprocess.check_output(['grep', 'timezone=GMT', '../docker/test-compose.yml'], encoding='UTF-8')

    ps = subprocess.run(
        ['grep', '-E', 'timezone=[^G]', '../docker/test-compose.yml'],
        check=False,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )
    assert ps.returncode == 1, print('Found GMT timestamps')

    ps = subprocess.run(
        ['grep', '-E', 'TZ=[^G]', '../docker/test-compose.yml'],
        check=False,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )
    assert ps.returncode == 1, print('Found GMT timestamps')
