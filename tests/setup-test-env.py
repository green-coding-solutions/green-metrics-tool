import os
from copy import deepcopy
import subprocess
import yaml

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib import utils

BASE_COMPOSE_NAME = 'compose.yml.example'
TEST_COMPOSE_NAME = 'test-compose.yml'

current_dir = os.path.abspath(os.path.dirname(__file__))
base_compose_path = os.path.join(current_dir, f"../docker/{BASE_COMPOSE_NAME}")
test_compose_path = os.path.join(current_dir, f"../docker/{TEST_COMPOSE_NAME}")

DB_PW = 'testpw'

def copy_sql_structure():
    print('Copying SQL structure...')
    subprocess.run(
        ['cp', '-f', '../docker/structure.sql', './structure.sql'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    if utils.get_architecture() == 'macos':
        command = ['sed', '-i', "", 's/green-coding/test-green-coding/g', './structure.sql']
    else:
        command = ['sed', '-i', 's/green-coding/test-green-coding/g', './structure.sql']

    subprocess.run(
        command,
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

def edit_compose_file():
    print('Creating test-compose.yml...')
    compose = None
    with open(base_compose_path, encoding='utf8') as base_compose_file:
        compose = yaml.load(base_compose_file, Loader=yaml.FullLoader)

    # Save old volume names, as we will have to look for them under services/volumes soon
    vol_keys = compose['volumes'].copy().keys()

    # Edit volume names with pre-pended 'test'
    for vol_name in compose.get('volumes').copy():
        compose['volumes'][f"test-{vol_name}"] = deepcopy(compose['volumes'][vol_name])
        del compose['volumes'][vol_name]

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

        # for nginx and gunicorn services, add test config mapping
        if 'nginx' in service or 'gunicorn' in service:
            new_vol_list.append(
                f'{current_dir}/test-config.yml:/var/www/green-metrics-tool/config.yml')
        compose['services'][service]['volumes'] = new_vol_list

        # For postgresql, change password
        if 'postgres' in service:
            new_env = []
            for env in compose['services'][service]['environment']:
                env = env.replace('PLEASE_CHANGE_THIS', DB_PW)
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


def edit_etc_hosts():
    subprocess.run(['./edit-etc-hosts.sh'], check=True)

def build_test_docker_image():
    subprocess.run(['docker', 'compose', '-f', test_compose_path, 'build'], check=True)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--no-docker-build', action='store_true',
                        help='Do not build the docker image')
    args = parser.parse_args()

    copy_sql_structure()
    edit_compose_file()
    edit_etc_hosts()
    if not args.no_docker_build:
        build_test_docker_image()
    print('fin.')
