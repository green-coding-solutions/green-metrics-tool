import yaml
import os
import re
from copy import deepcopy
import subprocess

base_config_name = 'config.yml'
base_compose_name = 'compose.yml.example'
test_config_name = 'test-config.yml'
test_compose_name = 'test-compose.yml'

db_pw = 'testpw'

current_dir = os.path.abspath(os.path.dirname(__file__))
base_config_path = os.path.join(current_dir, "../{base_config_name}".format(base_config_name=base_config_name))
base_compose_path = os.path.join(current_dir, "../docker/{base_compose_name}".format(base_compose_name=base_compose_name))
test_config_path = os.path.join(current_dir, "../{test_config_name}".format(test_config_name=test_config_name))
test_compose_path = os.path.join(current_dir, "../docker/{test_compose_name}".format(test_compose_name=test_compose_name))

def edit_config_file():
    print("Creating test-config.yml...")
    config = None
    with open(base_config_path) as base_config_file:
        config = yaml.load(base_config_file, Loader=yaml.FullLoader)

    # Reset SMTP
    for e in config.get('smtp'):
        config['smtp'][e] = None

    config['postgresql']['host'] = 'test-green-coding-postgres-container'
    config['postgresql']['password'] = db_pw
    config['admin']['no_emails'] = True

    with open(test_config_path, 'w') as test_config_file:
        yaml.dump(config, test_config_file)

def edit_compose_file():
    print("Creating test-compose.yml...")
    compose = None
    with open(base_compose_path) as base_compose_file:
        compose = yaml.load(base_compose_file, Loader=yaml.FullLoader)

    # Save old volume names, as we will have to look for them under services/volumes soon
    vol_keys = compose['volumes'].copy().keys()

    # Edit volume names with pre-pended 'test' 
    for e in compose.get('volumes').copy():
        compose['volumes']["test-{e}".format(e=e)] = deepcopy(compose['volumes'][e])
        del compose['volumes'][e]

    # Edit Services 
    for service in compose.get('services').copy():
        # Edit Services with new volumes
        service_volumes = compose['services'][service]['volumes'] 
        new_vol_list=[]
        for v in service_volumes:
            for k in vol_keys:
                v = v.replace(k,'test-{k}'.format(k=k))
            v = v.replace('PATH_TO_GREEN_METRICS_TOOL_REPO', '{cwd}/../'.format(cwd=current_dir))
            new_vol_list.append(v)

        ## Change the depends on: in services as well
        if 'depends_on' in compose['services'][service]:
            depends_on_list = compose['services'][service]['depends_on']
            new_depends_on_list=[]
            for d in depends_on_list:
                new_depends_on_list.append('test-{d}'.format(d=d))
            compose['services'][service]['depends_on'] = new_depends_on_list

        ## for nginx and gunicorn services, add test config mapping
        if 'nginx' in service or 'gunicorn' in service:
            new_vol_list.append('{cwd}/../test-config.yml:/var/www/green-metrics-tool/config.yml'.format(cwd=current_dir))
        compose['services'][service]['volumes'] = new_vol_list

        # For postgresql, change password
        if 'postgres' in service:
            new_env=[]
            for e in compose['services'][service]['environment']:
                e = e.replace('PLEASE_CHANGE_THIS', db_pw)
            new_env.append(e)
            compose['services'][service]['environment'] = new_env

        # Edit service container name
        old_container_name = compose['services'][service]['container_name']
        compose['services'][service]['container_name'] = 'test-{name}'.format(name=old_container_name)

        # Edit service names with pre-pended 'test'
        # Do this last so the changes done before are copied into new name
        new_key = "test-{e}".format(e=service)
        compose['services'][new_key] = deepcopy(compose['services'][service])
        del compose['services'][service]

    with open(test_compose_path, 'w') as test_compose_file:
        yaml.dump(compose, test_compose_file)

def edit_etc_hosts():
    subprocess.run(['./edit-etc-hosts.sh'])

if __name__ == "__main__":
    edit_config_file()
    edit_compose_file()
    edit_etc_hosts()
    print('fin.')