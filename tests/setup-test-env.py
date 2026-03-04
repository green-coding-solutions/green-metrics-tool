import os
from copy import deepcopy
import subprocess
import sys
from time import sleep
import yaml
import shutil
import re

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib import utils

BASE_COMPOSE_NAME = 'compose.yml.example'
TEST_COMPOSE_NAME = 'test-compose.yml'
BASE_FRONTEND_CONFIG_NAME = 'frontend/js/helpers/config.js.example'
OVERLAY_FRONTEND_CONFIG_NAME = 'frontend/js/helpers/config.js'
TEST_FRONTEND_CONFIG_NAME = 'test-config.js'
BASE_NGINX_PORT = 9142
TEST_NGINX_PORT = 9143
TEST_NGINX_PORT_MAPPING = [f"{TEST_NGINX_PORT}:{BASE_NGINX_PORT}"] # only change public port
BASE_DATABASE_PORT = 9573
TEST_DATABASE_PORT = 9574
TEST_DATABASE_PORT_MAPPING = [f"{TEST_DATABASE_PORT}:{TEST_DATABASE_PORT}"] # change external and internal port
TEST_REDIS_PORT = 6380 # original port: 6379
TEST_REDIS_PORT_MAPPING = [f"127.0.0.1:{TEST_REDIS_PORT}:{TEST_REDIS_PORT}"] # change external and internal port

current_dir = os.path.abspath(os.path.dirname(__file__))
base_compose_path = os.path.join(current_dir, f"../docker/{BASE_COMPOSE_NAME}")
test_compose_path = os.path.join(current_dir, f"../docker/{TEST_COMPOSE_NAME}")
base_frontend_config_path = os.path.join(current_dir, f'../{BASE_FRONTEND_CONFIG_NAME}')
test_frontend_config_path = os.path.join(current_dir, TEST_FRONTEND_CONFIG_NAME)

DB_PW = 'testpw'

def check_sudo():
    print('Checking sudo...')
    process = None
    try:
        process = subprocess.Popen(['sudo', 'echo', 'ok']) # pylint: disable=consider-using-with
        process.wait()
        if process.returncode != 0:
            raise RuntimeError("Failed to run sudo. Please run `sudo echo 'ok'` to get the sudo token and then rerun this script.")
    except KeyboardInterrupt:
        if process is not None:
            process.terminate()
        print('Interrupted by user. You might get some sudo message in your shell. Ignore it! Sleeping for 5 seconds to let sudo finish writing to terminal.')
        print("Failed to run sudo. Please run `sudo echo 'ok'` to get the sudo token and then rerun this script.")

        sleep(5) # We need to sleep here to give sudo time to write to terminal

        sys.exit(1)

def copy_sql_structure(ee=False):
    print('Copying SQL structure...')
    shutil.copyfile('../docker/structure.sql', './structure.sql')

    if ee:
        with open('../ee/docker/structure_ee.sql', 'r', encoding='utf-8') as source, open('./structure.sql', 'a', encoding='utf-8') as target:
            target.write(source.read())
            print("Enterprise DB definitions of '../ee/docker/structure.sql' appended to './structure.sql' successfully.")

    if utils.get_architecture() == 'macos':
        command = ['sed', '-i', "", 's/green-coding/test-green-coding/g', './structure.sql']
    else:
        command = ['sed', '-i', 's/green-coding/test-green-coding/g', './structure.sql']

    subprocess.check_output(command)


def edit_compose_file():
    print('Creating test-compose.yml...')
    compose = None
    with open(base_compose_path, encoding='utf8') as base_compose_file:
        compose = yaml.load(base_compose_file, Loader=yaml.FullLoader)

    # Edit stack name
    compose['name'] = 'green-metrics-tool-test'

    # Save old volume names, as we will have to look for them under services/volumes soon
    vol_keys = compose['volumes'].copy().keys()

    # Edit volume names with pre-pended 'test'
    for vol_name in compose.get('volumes').copy():
        compose['volumes'][f"test-{vol_name}"] = deepcopy(compose['volumes'][vol_name])
        del compose['volumes'][vol_name]

    tz_value = detect_timezone()


    # Edit Services
    for service in compose.get('services').copy():
        # Edit Services with new volumes
        service_volumes = compose['services'][service]['volumes']
        new_vol_list = []
        for volume in service_volumes:
            for k in vol_keys:
                volume = volume.replace(k, f'test-{k}')
            volume = volume.replace('PATH_TO_GREEN_METRICS_TOOL_REPO',
                          f'{current_dir}/../')
            volume = volume.replace('./structure.sql', '../tests/structure.sql')
            new_vol_list.append(volume)

        # Change the depends on: in services as well
        if 'depends_on' in compose['services'][service]:
            new_depends_on_list = []
            for dep in compose['services'][service]['depends_on']:
                new_depends_on_list.append(f'test-{dep}')
            compose['services'][service]['depends_on'] = new_depends_on_list

        # for nginx, change port mapping
        if 'nginx' in service:
            compose['services'][service]['ports'] = TEST_NGINX_PORT_MAPPING
            new_vol_list.append(
                f'{current_dir}/{TEST_FRONTEND_CONFIG_NAME}:/var/www/green-metrics-tool/{OVERLAY_FRONTEND_CONFIG_NAME}')

        # for nginx and gunicorn services, add test config and frontend config mapping
        if 'nginx' in service or 'gunicorn' in service:
            new_vol_list.append(
                f'{current_dir}/test-config.yml:/var/www/green-metrics-tool/config.yml')

        compose['services'][service]['volumes'] = new_vol_list

        # For postgresql, change port mapping and password
        if 'postgres' in service:
            command = compose['services'][service]['command']
            new_command = command.replace(str(BASE_DATABASE_PORT), str(TEST_DATABASE_PORT))
            new_command = new_command.replace('__TZ__', tz_value) # timezone in command string must go extra
            compose['services'][service]['command'] = new_command
            compose['services'][service]['ports'] = TEST_DATABASE_PORT_MAPPING

            new_env = []
            for env in compose['services'][service]['environment']:
                env = env.replace('PLEASE_CHANGE_THIS', DB_PW)
                new_env.append(env)
            compose['services'][service]['environment'] = new_env

        # For redis, change port mapping
        if 'redis' in service:
            command = compose['services'][service]['command']
            new_command = f'{command} --port {TEST_REDIS_PORT}'
            compose['services'][service]['command'] = new_command
            compose['services'][service]['ports'] = TEST_REDIS_PORT_MAPPING

        # For all, change time zone in env vars
        new_env = []
        for env in compose['services'][service]['environment']:
            env = env.replace('__TZ__', tz_value)
            new_env.append(env)
        compose['services'][service]['environment'] = new_env

        # Edit service container name
        old_container_name = compose['services'][service]['container_name']
        compose['services'][service]['container_name'] = f'test-{old_container_name}'

        # Edit service names with pre-pended 'test'
        # Do this last so the changes done before are copied into new name
        compose['services'][f"test-{service}"] = deepcopy(compose['services'][service])
        del compose['services'][service]

    with open(test_compose_path, 'w', encoding='utf8') as test_compose_file:
        yaml.dump(compose, test_compose_file)

def create_test_config_file(ee=False, ai=False):
    print('Creating test-config.yml...')

    with open('test-config.yml.example', 'r', encoding='utf-8') as file:
        content = file.read()

    content = content.replace('activate_eco_ci: False', 'activate_eco_ci: True')
    content = content.replace('activate_power_hog: False', 'activate_power_hog: True')
    content = content.replace('activate_carbon_db: False', 'activate_carbon_db: True')

    if ee:
        print('Activating enterprise in config.yml ...')
        content = content.replace('#ee_token:', 'ee_token:')

    if ai:
        print('Activating AI in config.yml ...')
        content = content.replace('activate_ai_optimisations: False', 'activate_ai_optimisations: True')

    with open('test-config.yml', 'w', encoding='utf-8') as file:
        file.write(content)

def create_frontend_config_file(ee=False, ai=False):
    print('Creating frontend test-config.js file...')

    with open(base_frontend_config_path, 'r', encoding='utf-8') as file:
        content = file.read()

    content = content.replace('__API_URL__', 'http://api.green-coding.internal:9143')
    content = content.replace('__METRICS_URL__', 'http://metrics.green-coding.internal:9143')
    content = content.replace('__ELEPHANT_URL__', 'http://elephant.green-coding.internal:8085')

    content = re.sub(r'ACTIVATE_SCENARIO_RUNNER.*$', 'ACTIVATE_SCENARIO_RUNNER = true;', content, flags=re.MULTILINE)
    content = re.sub(r'ACTIVATE_ECO_CI.*$', 'ACTIVATE_ECO_CI = true;', content, flags=re.MULTILINE)
    content = re.sub(r'ACTIVATE_CARBON_DB.*$', 'ACTIVATE_CARBON_DB = true;', content, flags=re.MULTILINE)
    content = re.sub(r'ACTIVATE_POWER_HOG.*$', 'ACTIVATE_POWER_HOG = true;', content, flags=re.MULTILINE)

    if ee:
        pass # currently noop as all non ai enterprise content has been moved to open source

    if ai:
        print(f'Activating AI in {TEST_FRONTEND_CONFIG_NAME} ...')
        content = re.sub(r'ACTIVATE_AI_OPTIMISATIONS.*$', 'ACTIVATE_AI_OPTIMISATIONS = true;', content, flags=re.MULTILINE)
    else:
        content = re.sub(r'ACTIVATE_AI_OPTIMISATIONS.*$', 'ACTIVATE_AI_OPTIMISATIONS = false;', content, flags=re.MULTILINE)

    with open(test_frontend_config_path, 'w', encoding='utf-8') as file:
        file.write(content)

def edit_etc_hosts():
    subprocess.run(['./edit-etc-hosts.sh'], check=True)


def build_test_docker_image():
    subprocess.run(['docker', 'compose', '-f', test_compose_path, 'build'], check=True)

def pull_test_docker_image():
    subprocess.run(['docker', 'compose', '-f', test_compose_path, 'pull'], check=True)

# We never want to set a different timezone than GMT for tests.
# The reason being is that we have a lot of demo data with GMT timestamps in the DB and this
# should always be tested against a system running on GMT. Otherwise users in different timezones will experience failing tests
def detect_timezone(): # default="Europe/Berlin"
    return 'GMT'

    # if os.path.isfile("/etc/timezone"):
    #     with open("/etc/timezone", encoding="utf-8") as f:
    #         tz = f.read().strip()
    #         if tz:
    #             return tz

    # if os.path.exists("/etc/localtime"):
    #     real = os.path.realpath("/etc/localtime")
    #     if "zoneinfo.default/" in real:
    #         return real.split("zoneinfo.default/")[-1]
    #     elif "zoneinfo/" in real:
    #         return real.split("zoneinfo/")[-1]
    # return default


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--no-docker-build', action='store_true',
                        help='Do not build the docker image')
    parser.add_argument('--no-docker-pull', action='store_true',
                        help='Do not pull the docker images')
    parser.add_argument('--ee', action='store_true',
                        help='Enable enterprise tests')
    parser.add_argument('--ai', action='store_true',
                        help='Enable AI tests')


    args = parser.parse_args()

    check_sudo()
    copy_sql_structure(args.ee)
    create_test_config_file(args.ee, args.ai)
    create_frontend_config_file(args.ee, args.ai)
    edit_compose_file()
    edit_etc_hosts()
    if not args.no_docker_pull:
        pull_test_docker_image()
    if not args.no_docker_build:
        build_test_docker_image()
    subprocess.check_output(['sudo', '-k']) # deactivate sudo again
    print('fin.')
