#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

from lib.venv_checker import check_venv
check_venv() # this check must even run before __main__ as imports might not get resolved

import subprocess
import json
import os
import time
from datetime import datetime
from html import escape
import sys
import importlib
import re
from io import StringIO
from pathlib import Path
import random
import shutil
import yaml


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib import utils
from lib import process_helpers
from lib import hardware_info
from lib import hardware_info_root
from lib import error_helpers
from lib.debug_helper import DebugHelper
from lib.terminal_colors import TerminalColors
from lib.schema_checker import SchemaChecker
from lib.db import DB
from lib.global_config import GlobalConfig
from lib.notes import Notes
from lib import system_checks

from tools.machine import Machine

def arrows(text):
    return f"\n\n>>>> {text} <<<<\n\n"

# This function takes a path and a file and joins them while making sure that no one is trying to escape the
# path with `..`, symbolic links or similar.
# We always return the same error message including the path and file parameter, never `filename` as
# otherwise we might disclose if certain files exist or not.
def join_paths(path, path2, mode=None):
    filename = os.path.realpath(os.path.join(path, path2))

    # If the original path is a symlink we need to resolve it.
    path = os.path.realpath(path)

    # This is a special case in which the file is '.'
    if filename == path.rstrip('/'):
        return filename

    if not filename.startswith(path):
        raise ValueError(f"{path2} not in {path}")

    # To double check we also check if it is in the files allow list

    if mode == 'file':
        folder_content = [str(item) for item in Path(path).rglob("*") if item.is_file()]
    elif mode == 'dir':
        folder_content = [str(item) for item in Path(path).rglob("*") if item.is_dir()]
    else:
        folder_content = [str(item) for item in Path(path).rglob("*")]

    if filename not in folder_content:
        raise ValueError(f"{path2} not in {path}")

    # Another way to implement this. This is checking the third time but we want to be extra secure 👾
    if Path(path).resolve(strict=True) not in Path(path, path2).resolve(strict=True).parents:
        raise ValueError(f"{path2} not in {path}")

    if os.path.exists(filename):
        return filename

    raise FileNotFoundError(f"{path2} in {path} not found")



class Runner:
    def __init__(self,
        name, uri, uri_type, filename='usage_scenario.yml', branch=None,
        debug_mode=False, allow_unsafe=False, no_file_cleanup=False, skip_system_checks=False,
        skip_unsafe=False, verbose_provider_boot=False, full_docker_prune=False,
        dry_run=False, dev_repeat_run=False, docker_prune=False, job_id=None):

        if skip_unsafe is True and allow_unsafe is True:
            raise RuntimeError('Cannot specify both --skip-unsafe and --allow-unsafe')

        # variables that should not change if you call run multiple times
        self._name = name
        self._debugger = DebugHelper(debug_mode)
        self._allow_unsafe = allow_unsafe
        self._no_file_cleanup = no_file_cleanup
        self._skip_unsafe = skip_unsafe
        self._skip_system_checks = skip_system_checks
        self._verbose_provider_boot = verbose_provider_boot
        self._full_docker_prune = full_docker_prune
        self._docker_prune = docker_prune
        self._dry_run = dry_run
        self._dev_repeat_run = dev_repeat_run
        self._uri = uri
        self._uri_type = uri_type
        self._original_filename = filename
        self._branch = branch
        self._tmp_folder = '/tmp/green-metrics-tool'
        self._usage_scenario = {}
        self._architecture = utils.get_architecture()
        self._sci = {'R_d': None, 'R': 0}
        self._job_id = job_id
        self._arguments = locals()
        del self._arguments['self'] # self is not needed and also cannot be serialzed. We remove it


        # transient variables that are created by the runner itself
        # these are accessed and processed on cleanup and then reset
        # They are __ as they should not be changed because this could break the state of the runner
        self.__stdout_logs = {}
        self.__containers = {}
        self.__networks = []
        self.__ps_to_kill = []
        self.__ps_to_read = []
        self.__metric_providers = []
        self.__notes_helper = Notes()
        self.__phases = {}
        self.__start_measurement = None
        self.__end_measurement = None
        self.__services_to_pause_phase = {}
        self.__join_default_network = False
        self.__docker_params = []
        self.__folder = f"{self._tmp_folder}/repo" # default if not changed in checkout_repository
        self.__run_id = None

        # we currently do not use this variable
        # self.__filename = self._original_filename # this can be changed later if working directory changes

    def custom_sleep(self, sleep_time):
        if not self._dry_run:
            print(TerminalColors.HEADER, '\nSleeping for : ', sleep_time, TerminalColors.ENDC)
            time.sleep(sleep_time)

    def initialize_run(self):
            # We issue a fetch_one() instead of a query() here, cause we want to get the RUN_ID
        self.__run_id = DB().fetch_one("""
                INSERT INTO runs (job_id, name, uri, email, branch, runner_arguments, created_at)
                VALUES (%s, %s, %s, 'manual', %s, %s, NOW())
                RETURNING id
                """, params=(self._job_id, self._name, self._uri, self._branch, json.dumps(self._arguments)))[0]
        return self.__run_id

    def initialize_folder(self, path):
        shutil.rmtree(path, ignore_errors=True)
        Path(path).mkdir(parents=True, exist_ok=True)

    def save_notes_runner(self):
        print(TerminalColors.HEADER, '\nSaving notes: ', TerminalColors.ENDC, self.__notes_helper.get_notes())
        self.__notes_helper.save_to_db(self.__run_id)

    def check_system(self, mode='start'):
        if self._skip_system_checks:
            print("System check skipped")
            return

        if mode =='start':
            system_checks.check_start()
        else:
            raise RuntimeError('Unknown mode for system check:', mode)


    def checkout_repository(self):
        print(TerminalColors.HEADER, '\nChecking out repository', TerminalColors.ENDC)

        if self._uri_type == 'URL':
            # always remove the folder if URL provided, cause -v directory binding always creates it
            # no check cause might fail when directory might be missing due to manual delete
            if self._branch:
                print(f"Branch specified: {self._branch}")
                # git clone -b <branchname> --single-branch <remote-repo-url>
                subprocess.run(
                    [
                        'git',
                        'clone',
                        '--depth', '1',
                        '-b', self._branch,
                        '--single-branch',
                        '--recurse-submodules',
                        '--shallow-submodules',
                        self._uri,
                        self.__folder
                    ],
                    check=True,
                    capture_output=True,
                    encoding='UTF-8',
                )
            else:
                subprocess.run(
                    [
                        'git',
                        'clone',
                        '--depth', '1',
                        '--single-branch',
                        '--recurse-submodules',
                        '--shallow-submodules',
                        self._uri,
                        self.__folder
                    ],
                    check=True,
                    capture_output=True,
                    encoding='UTF-8'
                )  # always name target-dir repo according to spec

        else:
            if self._branch:
                raise RuntimeError('Specified --branch but using local URI. Did you mean to specify a github url?')
            self.__folder = self._uri

        # we can safely do this, even with problematic folders, as the folder can only be a local unsafe one when
        # running in CLI mode
        commit_hash = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            check=True,
            capture_output=True,
            encoding='UTF-8',
            cwd=self.__folder
        )
        commit_hash = commit_hash.stdout.strip("\n")

        commit_timestamp = subprocess.run(
            ['git', 'show', '-s', '--format=%ci'],
            check=True,
            capture_output=True,
            encoding='UTF-8',
            cwd=self.__folder
        )
        commit_timestamp = commit_timestamp.stdout.strip("\n")
        parsed_timestamp = datetime.strptime(commit_timestamp, "%Y-%m-%d %H:%M:%S %z")

        DB().query("""
            UPDATE runs
            SET
                commit_hash=%s,
                commit_timestamp=%s
            WHERE id = %s
            """, params=(commit_hash, parsed_timestamp, self.__run_id))

    # This method loads the yml file and takes care that the includes work and are secure.
    # It uses the tagging infrastructure provided by https://pyyaml.org/wiki/PyYAMLDocumentation
    # Inspiration from https://github.com/tanbro/pyyaml-include which we can't use as it doesn't
    # do security checking and has no option to select when imported
    def load_yml_file(self):
        #pylint: disable=too-many-ancestors
        class Loader(yaml.SafeLoader):
            def __init__(self, stream):
                # We need to find our own root as the Loader is instantiated in PyYaml
                self._root = os.path.split(stream.name)[0]
                super().__init__(stream)

            def include(self, node):
                # We allow two types of includes
                # !include <filename> => ScalarNode
                # and
                # !include <filename> <selector> => SequenceNode
                if isinstance(node, yaml.nodes.ScalarNode):
                    nodes = [self.construct_scalar(node)]
                elif isinstance(node, yaml.nodes.SequenceNode):
                    nodes = self.construct_sequence(node)
                else:
                    raise ValueError("We don't support Mapping Nodes to date")

                filename = join_paths(self._root, nodes[0], 'file')

                with open(filename, 'r', encoding='utf-8') as f:
                    # We want to enable a deep search for keys
                    def recursive_lookup(k, d):
                        if k in d:
                            return d[k]
                        for v in d.values():
                            if isinstance(v, dict):
                                return recursive_lookup(k, v)
                        return None

                    # We can use load here as the Loader extends SafeLoader
                    if len(nodes) == 1:
                        # There is no selector specified
                        return yaml.load(f, Loader)

                    return recursive_lookup(nodes[1], yaml.load(f, Loader))

        Loader.add_constructor('!include', Loader.include)

        usage_scenario_file = join_paths(self.__folder, self._original_filename, 'file')

        # We set the working folder now to the actual location of the usage_scenario
        if '/' in self._original_filename:
            self.__folder = usage_scenario_file.rsplit('/', 1)[0]
            #self.__filename = usage_scenario_file.rsplit('/', 1)[1] # we currently do not use this variable
            print("Working folder changed to ", self.__folder)


        with open(usage_scenario_file, 'r', encoding='utf-8') as fp:
            # We can use load here as the Loader extends SafeLoader
            yml_obj = yaml.load(fp, Loader)
            # Now that we have parsed the yml file we need to check for the special case in which we have a
            # compose-file key. In this case we merge the data we find under this key but overwrite it with
            # the data from the including file.

            # We need to write our own merge method as dict.update doesn't do a "deep" merge
            def merge_dicts(dict1, dict2):
                if isinstance(dict1, dict):
                    for k, v in dict2.items():
                        if k in dict1 and isinstance(v, dict) and isinstance(dict1[k], dict):
                            merge_dicts(dict1[k], v)
                        else:
                            dict1[k] = v
                    return dict1
                return dict1

            new_dict = {}
            if 'compose-file' in yml_obj.keys():
                for k,v in yml_obj['compose-file'].items():
                    if k in yml_obj:
                        new_dict[k] = merge_dicts(v,yml_obj[k])
                    else: # just copy over if no key exists in usage_scenario
                        yml_obj[k] = v

                del yml_obj['compose-file']

            yml_obj.update(new_dict)

            # If a service is defined as None we remove it. This is so we can have a compose file that starts
            # all the various services but we can disable them in the usage_scenario. This is quite useful when
            # creating benchmarking scripts and you want to have all options in the compose but not in each benchmark.
            # The cleaner way would be to handle an empty service key throughout the code but would make it quite messy
            # so we chose to remove it right at the start.
            for key in [sname for sname, content in yml_obj['services'].items() if content is None]:
                del yml_obj['services'][key]

            self._usage_scenario = yml_obj

    def initial_parse(self):

        self.load_yml_file()

        schema_checker = SchemaChecker(validate_compose_flag=True)
        schema_checker.check_usage_scenario(self._usage_scenario)

        print(TerminalColors.HEADER, '\nHaving Usage Scenario ', self._usage_scenario['name'], TerminalColors.ENDC)
        print('From: ', self._usage_scenario['author'])
        print('Description: ', self._usage_scenario['description'], '\n')

        if self._allow_unsafe:
            print(TerminalColors.WARNING, arrows('Warning: Runner is running in unsafe mode'), TerminalColors.ENDC)

        if self._usage_scenario.get('architecture') is not None and self._architecture != self._usage_scenario['architecture'].lower():
            raise RuntimeError(f"Specified architecture does not match system architecture: system ({self._architecture}) != specified ({self._usage_scenario.get('architecture')})")

        self._sci['R_d'] = self._usage_scenario.get('sci', {}).get('R_d', None)

    def check_running_containers(self):
        result = subprocess.run(['docker', 'ps' ,'--format', '{{.Names}}'],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                check=True, encoding='UTF-8')
        for line in result.stdout.splitlines():
            for running_container in line.split(','): # if docker container has multiple tags, they will be split by comma, so we only want to
                for service_name in self._usage_scenario.get('services', []):
                    if 'container_name' in self._usage_scenario['services'][service_name]:
                        container_name = self._usage_scenario['services'][service_name]['container_name']
                    else:
                        container_name = service_name

                    if running_container == container_name:
                        raise PermissionError(f"Container '{container_name}' is already running on system. Please close it before running the tool.")

    def populate_image_names(self):
        for service_name, service in self._usage_scenario.get('services', []).items():
            if not service.get('image', None): # image is a non essential field. But we need it, so we tmp it
                if self._dev_repeat_run:
                    service['image'] = f"{service_name}"
                else:
                    service['image'] = f"{service_name}_{random.randint(500000,10000000)}"

    def remove_docker_images(self):
        if self._dev_repeat_run:
            return

        print(TerminalColors.HEADER, '\nRemoving all temporary GMT images', TerminalColors.ENDC)
        subprocess.run(
            'docker images --format "{{.Repository}}:{{.Tag}}" | grep "gmt_run_tmp" | xargs docker rmi -f',
            shell=True,
            stderr=subprocess.DEVNULL, # to suppress showing of stderr
            check=False,
        )

        if self._full_docker_prune:
            print(TerminalColors.HEADER, '\nStopping and removing all containers, build caches, volumes and images on the system', TerminalColors.ENDC)
            subprocess.run('docker ps -aq | xargs docker stop', shell=True, check=False)
            subprocess.run('docker images --format "{{.ID}}" | xargs docker rmi -f', shell=True, check=False)
            subprocess.run(['docker', 'system', 'prune' ,'--force', '--volumes'], check=True)
        elif self._docker_prune:
            print(TerminalColors.HEADER, '\nRemoving all unassociated build caches, networks volumes and stopped containers on the system', TerminalColors.ENDC)
            subprocess.run(['docker', 'system', 'prune' ,'--force', '--volumes'], check=True)
        else:
            print(TerminalColors.WARNING, arrows('Warning: GMT is not instructed to prune docker images and build caches. \nWe recommend to set --docker-prune to remove build caches and anonymous volumes, because otherwise your disk will get full very quickly. If you want to measure also network I/O delay for pulling images and have a dedicated measurement machine please set --full-docker-prune'), TerminalColors.ENDC)

    '''
        A machine will always register in the database on run.
        This means that it will write its machine_id and machine_descroption to the machines table
        and then link itself in the runs table accordingly.
    '''
    def register_machine_id(self):
        config = GlobalConfig().config
        if config['machine'].get('id') is None \
            or not isinstance(config['machine']['id'], int) \
            or config['machine'].get('description') is None \
            or config['machine']['description'] == '':
            raise RuntimeError('You must set machine id and machine description')

        machine = Machine(machine_id=config['machine'].get('id'), description=config['machine'].get('description'))
        machine.register()

    def update_and_insert_specs(self):
        config = GlobalConfig().config

        gmt_hash = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            check=True,
            capture_output=True,
            encoding='UTF-8',
            cwd=CURRENT_DIR
        )
        gmt_hash = gmt_hash.stdout.strip("\n")


        # There are two ways we get hardware info. First things we don't need to be root to do which we get through
        # a method call. And then things we need root privilege which we need to call as a subprocess with sudo. The
        # install.sh script should have added the script to the sudoes file.
        machine_specs = hardware_info.get_default_values()

        if len(hardware_info_root.get_root_list()) > 0:
            python_file = os.path.abspath(os.path.join(CURRENT_DIR, 'lib/hardware_info_root.py'))
            ps = subprocess.run(['sudo', sys.executable, python_file], stdout=subprocess.PIPE, check=True, encoding='UTF-8')
            machine_specs_root = json.loads(ps.stdout)

            machine_specs.update(machine_specs_root)


        keys = ["measurement", "sci"]
        measurement_config = {key: config.get(key, None) for key in keys}

        # Insert auxilary info for the run. Not critical.
        DB().query("""
            UPDATE runs
            SET
                machine_id=%s, machine_specs=%s, measurement_config=%s,
                usage_scenario = %s, filename=%s, gmt_hash=%s
            WHERE id = %s
            """, params=(
            config['machine']['id'],
            escape(json.dumps(machine_specs), quote=False),
            json.dumps(measurement_config),
            escape(json.dumps(self._usage_scenario), quote=False),
            self._original_filename,
            gmt_hash,
            self.__run_id)
        )

    def import_metric_providers(self):
        config = GlobalConfig().config

        print(TerminalColors.HEADER, '\nImporting metric providers', TerminalColors.ENDC)

        metric_providers = utils.get_metric_providers(config)

        if not metric_providers:
            print(TerminalColors.WARNING, arrows('No metric providers were configured in config.yml. Was this intentional?'), TerminalColors.ENDC)
            return

        docker_ps = subprocess.run(["docker", "info"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, encoding='UTF-8', check=True)
        rootless = False
        if 'rootless' in docker_ps.stdout:
            rootless = True

        for metric_provider in metric_providers: # will iterate over keys
            module_path, class_name = metric_provider.rsplit('.', 1)
            module_path = f"metric_providers.{module_path}"
            conf = metric_providers[metric_provider] or {}

            if rootless and '.cgroup.' in module_path:
                conf['rootless'] = True

            print(f"Importing {class_name} from {module_path}")
            print(f"Configuration is {conf}")

            module = importlib.import_module(module_path)

            metric_provider_obj = getattr(module, class_name)(**conf)

            self.__metric_providers.append(metric_provider_obj)

            if hasattr(metric_provider_obj, 'get_docker_params'):
                services_list = ",".join(list(self._usage_scenario['services'].keys()))
                self.__docker_params += metric_provider_obj.get_docker_params(no_proxy_list=services_list)


        self.__metric_providers.sort(key=lambda item: 'rapl' not in item.__class__.__name__.lower())

    def download_dependencies(self):
        print(TerminalColors.HEADER, '\nDownloading dependencies', TerminalColors.ENDC)
        subprocess.run(['docker', 'pull', 'gcr.io/kaniko-project/executor:latest'], check=True)

    def get_build_info(self, service):
        if isinstance(service['build'], str):
            # If build is a string we can assume the short form
            context = service['build']
            dockerfile = 'Dockerfile'
        else:
            context =  service['build'].get('context', '.')
            dockerfile = service['build'].get('dockerfile', 'Dockerfile')

        return context, dockerfile

    def clean_image_name(self, name):
        # clean up image name for problematic characters
        name = re.sub(r'[^A-Za-z0-9_]', '', name)
        name = f"{name}_gmt_run_tmp"
        return name

    def build_docker_images(self):
        print(TerminalColors.HEADER, '\nBuilding Docker images', TerminalColors.ENDC)

        # Create directory /tmp/green-metrics-tool/docker_images
        temp_dir = f"{self._tmp_folder}/docker_images"
        self.initialize_folder(temp_dir)

        # technically the usage_scenario needs no services and can also operate on an empty list
        # This use case is when you have running containers on your host and want to benchmark some code running in them
        for _, service in self._usage_scenario.get('services', []).items():
            # minimal protection from possible shell escapes.
            # since we use subprocess without shell we should be safe though
            if re.findall(r'(\.\.|\$|\'|"|`|!)', service['image']):
                raise ValueError(f"In scenario file the builds contains an invalid image name: {service['image']}")

            tmp_img_name = self.clean_image_name(service['image'])

            #If we are in developer repeat runs check if the docker image has already been built
            try:
                subprocess.run(['docker', 'inspect', '--type=image', tmp_img_name],
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE,
                                         encoding='UTF-8',
                                         check=True)
                # The image exists so exit and don't build
                continue
            except subprocess.CalledProcessError:
                pass

            if 'build' in service:
                context, dockerfile = self.get_build_info(service)
                print(f"Building {service['image']}")
                self.__notes_helper.add_note({'note': f"Building {service['image']}", 'detail_name': '[NOTES]', 'timestamp': int(time.time_ns() / 1_000)})

                # Make sure the context docker file exists and is not trying to escape some root. We don't need the returns
                context_path = join_paths(self.__folder, context, 'dir')
                join_paths(context_path, dockerfile, 'file')

                docker_build_command = ['docker', 'run', '--rm',
                    '-v', f"{self.__folder}:/workspace:ro", # this is the folder where the usage_scenario is!
                    '-v', f"{temp_dir}:/output",
                    'gcr.io/kaniko-project/executor:latest',
                    f"--dockerfile=/workspace/{context}/{dockerfile}",
                    '--context', f'dir:///workspace/{context}',
                    f"--destination={tmp_img_name}",
                    f"--tar-path=/output/{tmp_img_name}.tar",
                    '--no-push']

                if self.__docker_params:
                    docker_build_command[2:2] = self.__docker_params

                print(" ".join(docker_build_command))

                ps = subprocess.run(docker_build_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='UTF-8', check=False)

                if ps.returncode != 0:
                    print(f"Error: {ps.stderr} \n {ps.stdout}")
                    raise OSError(f"Docker build failed\nStderr: {ps.stderr}\nStdout: {ps.stdout}")

                # import the docker image locally
                image_import_command = ['docker', 'load', '-q', '-i', f"{temp_dir}/{tmp_img_name}.tar"]
                print(" ".join(image_import_command))
                ps = subprocess.run(image_import_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='UTF-8', check=False)

                if ps.returncode != 0 or ps.stderr != "":
                    print(f"Error: {ps.stderr} \n {ps.stdout}")
                    raise OSError("Docker image import failed")

            else:
                print(f"Pulling {service['image']}")
                self.__notes_helper.add_note({'note':f"Pulling {service['image']}" , 'detail_name': '[NOTES]', 'timestamp': int(time.time_ns() / 1_000)})
                ps = subprocess.run(['docker', 'pull', service['image']], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='UTF-8', check=False)

                if ps.returncode != 0:
                    print(f"Error: {ps.stderr} \n {ps.stdout}")
                    raise OSError(f"Docker pull failed. Is your image name correct and are you connected to the internet: {service['image']}")

                # tagging must be done in pull case, so we cann the correct container later
                subprocess.run(['docker', 'tag', service['image'], tmp_img_name], check=True)


        # Delete the directory /tmp/gmt_docker_images
        shutil.rmtree(temp_dir)


    def setup_networks(self):
        # for some rare containers there is no network, like machine learning for example
        if 'networks' in self._usage_scenario:
            print(TerminalColors.HEADER, '\nSetting up networks', TerminalColors.ENDC)
            for network in self._usage_scenario['networks']:
                print('Creating network: ', network)
                # remove first if present to not get error, but do not make check=True, as this would lead to inf. loop
                subprocess.run(['docker', 'network', 'rm', network], stderr=subprocess.DEVNULL, check=False)
                subprocess.run(['docker', 'network', 'create', network], check=True)
                self.__networks.append(network)
        else:
            print(TerminalColors.HEADER, '\nNo network found. Creating default network', TerminalColors.ENDC)
            network = f"GMT_default_tmp_network_{random.randint(500000,10000000)}"
            print('Creating network: ', network)
            # remove first if present to not get error, but do not make check=True, as this would lead to inf. loop
            subprocess.run(['docker', 'network', 'rm', network], stderr=subprocess.DEVNULL, check=False)
            subprocess.run(['docker', 'network', 'create', network], check=True)
            self.__networks.append(network)
            self.__join_default_network = True

    def setup_services(self):
        # technically the usage_scenario needs no services and can also operate on an empty list
        # This use case is when you have running containers on your host and want to benchmark some code running in them
        for service_name in self._usage_scenario.get('services', []):
            print(TerminalColors.HEADER, '\nSetting up containers', TerminalColors.ENDC)

            if 'container_name' in self._usage_scenario['services'][service_name]:
                container_name = self._usage_scenario['services'][service_name]['container_name']
            else:
                container_name = service_name

            service = self._usage_scenario['services'][service_name]

            print('Resetting container')
            # By using the -f we return with 0 if no container is found
            # we always reset container without checking if something is running, as we expect that a user understands
            # this mechanic when using docker based tools. A container with the same name may not run twice
            subprocess.run(['docker', 'rm', '-f', container_name], stderr=subprocess.DEVNULL, check=True)

            print('Creating container')
            # We are attaching the -it option here to keep STDIN open and a terminal attached.
            # This helps to keep an excecutable-only container open, which would otherwise exit
            # This MAY break in the future, as some docker CLI implementation do not allow this and require
            # the command args to be passed on run only

            # docker_run_string must stay as list, cause this forces items to be quoted and escaped and prevents
            # injection of unwawnted params
            docker_run_string = ['docker', 'run', '-it', '-d', '--name', container_name]

            docker_run_string.append('-v')
            if 'folder-destination' in service:
                docker_run_string.append(f"{self.__folder}:{service['folder-destination']}:ro")
            else:
                docker_run_string.append(f"{self.__folder}:/tmp/repo:ro")

            if self.__docker_params:
                docker_run_string[2:2] = self.__docker_params


            if 'volumes' in service:
                if self._allow_unsafe:
                    # On old docker clients we experience some weird error, that we deem legacy
                    # If a volume is supplied in the compose.yml file in this form: ./file.txt:/tmp/file.txt
                    # and the file does NOT exist, then docker will create the folder in the current running dir
                    # This is however not enabled anymore and hard to circumvent. We keep this as unfixed for now.
                    if not isinstance(service['volumes'], list):
                        raise RuntimeError(f"Service '{service_name}' volumes must be a list but is: {type(service['volumes'])}")

                    for volume in service['volumes']:
                        docker_run_string.append('-v')
                        if volume.startswith('./'): # we have a bind-mount with relative path
                            vol = volume.split(':',1) # there might be an :ro etc at the end, so only split once
                            path = os.path.realpath(os.path.join(self.__folder, vol[0]))
                            if not os.path.exists(path):
                                raise RuntimeError(f"Service '{service_name}' volume path does not exist: {path}")
                            docker_run_string.append(f"{path}:{vol[1]}")
                        else:
                            docker_run_string.append(f"{volume}")
                else: # safe volume bindings are active by default
                    if not isinstance(service['volumes'], list):
                        raise RuntimeError(f"Service '{service_name}' volumes must be a list but is: {type(service['volumes'])}")
                    for volume in service['volumes']:
                        vol = volume.split(':')
                        # We always assume the format to be ./dir:dir:[flag] as if we allow none bind mounts people
                        # could create volumes that would linger on our system.
                        path = os.path.realpath(os.path.join(self.__folder, vol[0]))
                        if not os.path.exists(path):
                            raise RuntimeError(f"Service '{service_name}' volume path does not exist: {path}")

                        # Check that the path starts with self.__folder
                        if not path.startswith(self.__folder):
                            raise RuntimeError(f"Service '{service_name}' trying to escape folder: {path}")

                        # To double check we also check if it is in the files allow list
                        if path not in [str(item) for item in Path(self.__folder).rglob("*")]:
                            raise RuntimeError(f"Service '{service_name}' volume '{path}' not in allowed file list")

                        if len(vol) == 3:
                            if vol[2] != 'ro':
                                raise RuntimeError(f"Service '{service_name}': We only allow ro as parameter in volume mounts in unsafe mode")

                        docker_run_string.append('--mount')
                        docker_run_string.append(f"type=bind,source={path},target={vol[1]},readonly")

            if 'ports' in service:
                if self._allow_unsafe:
                    if not isinstance(service['ports'], list):
                        raise RuntimeError(f"ports must be a list but is: {type(service['ports'])}")
                    for ports in service['ports']:
                        print('Setting ports: ', service['ports'])
                        docker_run_string.append('-p')
                        docker_run_string.append(ports)
                elif self._skip_unsafe:
                    print(TerminalColors.WARNING, arrows('Found ports entry but not running in unsafe mode. Skipping'), TerminalColors.ENDC)
                else:
                    raise RuntimeError('Found "ports" but neither --skip-unsafe nor --allow-unsafe is set')

            if 'environment' in service:
                for docker_env_var in service['environment']:
                    # In a compose file env vars can be defined with a "=" and as a dict.
                    # We make sure that:
                    # environment:
                    #   - DEBUG
                    # or
                    # environment:
                    #   - image: "postgres: ${POSTGRES_VERSION}"
                    # will fail as this could expose env vars from the host system.
                    if isinstance(docker_env_var, str) and '=' in docker_env_var:
                        env_key, env_value = docker_env_var.split('=')
                    elif isinstance(service['environment'], dict):
                        env_key, env_value = str(docker_env_var), str(service['environment'][docker_env_var])
                    else:
                        raise RuntimeError('Environment variable needs to be a string with = or dict and non-empty. We do not allow the feature of forwarding variables from the host OS!')

                    if not self._allow_unsafe and re.search(r'^[A-Z_]+$', env_key) is None:
                        if self._skip_unsafe:
                            warn_message= arrows(f"Found environment var key with wrong format. Only ^[A-Z_]+$ allowed: {env_key} - Skipping")
                            print(TerminalColors.WARNING, warn_message, TerminalColors.ENDC)
                            continue
                        raise RuntimeError(f"Docker container setup environment var key had wrong format. Only ^[A-Z_]+$ allowed: {env_key} - Maybe consider using --allow-unsafe or --skip-unsafe")

                    if not self._allow_unsafe and \
                        re.search(r'^[a-zA-Z0-9_]+[a-zA-Z0-9_-]*$', env_value) is None:
                        if self._skip_unsafe:
                            print(TerminalColors.WARNING, arrows(f"Found environment var value with wrong format. Only ^[A-Z_]+[a-zA-Z0-9_]*$ allowed: {env_value} - Skipping"), TerminalColors.ENDC)
                            continue
                        raise RuntimeError(f"Docker container setup environment var value had wrong format. Only ^[A-Z_]+[a-zA-Z0-9_]*$ allowed: {env_value} - Maybe consider using --allow-unsafe --skip-unsafe")

                    docker_run_string.append('-e')
                    docker_run_string.append(f"{env_key}={env_value}")

            if 'networks' in service:
                for network in service['networks']:
                    docker_run_string.append('--net')
                    docker_run_string.append(network)
            elif self.__join_default_network:
                # only join default network if no other networks provided
                # if this is true only one entry is in self.__networks
                docker_run_string.append('--net')
                docker_run_string.append(self.__networks[0])


            if 'pause-after-phase' in service:
                self.__services_to_pause_phase[service['pause-after-phase']] = self.__services_to_pause_phase.get(service['pause-after-phase'], []) + [container_name]

            docker_run_string.append(self.clean_image_name(service['image']))

            if 'cmd' in service:  # must come last
                docker_run_string.append(service['cmd'])

            print(f"Running docker run with: {' '.join(docker_run_string)}")

            # docker_run_string must stay as list, cause this forces items to be quoted and escaped and prevents
            # injection of unwawnted params

            ps = subprocess.run(
                docker_run_string,
                check=True,
                stdout=subprocess.PIPE,
                #stderr=subprocess.DEVNULL, // not setting will show in CLI
                encoding='UTF-8'
            )

            container_id = ps.stdout.strip()
            self.__containers[container_id] = {
                'name': container_name,
                'log-stdout': service.get('log-stdout', False),
                'log-stderr': service.get('log-stderr', True),
                'read-sci-stdout': service.get('read-sci-stdout', False),
            }

            print('Stdout:', container_id)

            if 'setup-commands' not in service:
                continue  # setup commands are optional
            print('Running commands')
            for cmd in service['setup-commands']:
                if shell := service.get('shell', False):
                    d_command = ['docker', 'exec', container_name, shell, '-c', cmd] # This must be a list!
                else:
                    d_command = ['docker', 'exec', container_name, *cmd.split()] # This must be a list!

                print('Running command: ', ' '.join(d_command))

                # docker exec must stay as list, cause this forces items to be quoted and escaped and prevents
                # injection of unwawnted params
                ps = subprocess.run(
                    d_command,
                    check=True,
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    encoding='UTF-8'
                )
                print('Stdout:', ps.stdout)
                print('Stderr:', ps.stderr)

                if ps.stdout:
                    self.add_to_log(container_name, f"stdout {ps.stdout}", d_command)
                if ps.stderr:
                    self.add_to_log(container_name, f"stderr {ps.stderr}", d_command)

            # Obsolete warnings. But left in, cause reasoning for NotImplementedError still holds
            # elif el['type'] == 'Dockerfile':
            #    raise NotImplementedError('Green Metrics Tool can currently not consume Dockerfiles. \
            # This will be a premium feature, as it creates a lot of server usage and thus slows down \
            # Tests per Minute for our server.')
            # elif el['type'] == 'Docker-Compose':
            #    raise NotImplementedError('Green Metrics Tool will not support that, because we wont support \
            # all features from docker compose, like for instance volumes and binding arbitrary directories')
            # else:
            #    raise RuntimeError('Unknown type detected in setup: ', el.get('type', None))

        print(TerminalColors.HEADER, '\nCurrent known containers: ', self.__containers, TerminalColors.ENDC)

    def get_logs(self):
        return self.__stdout_logs

    def add_to_log(self, container_name, message, cmd=''):
        log_entry_name = f"{container_name}_{cmd}"
        if log_entry_name not in self.__stdout_logs:
            self.__stdout_logs[log_entry_name] = ''
        self.__stdout_logs[log_entry_name] = '\n'.join((self.__stdout_logs[log_entry_name], message))


    def start_metric_providers(self, allow_container=True, allow_other=True):
        print(TerminalColors.HEADER, '\nStarting metric providers', TerminalColors.ENDC)

        for metric_provider in self.__metric_providers:
            if metric_provider._metric_name.endswith('_container') and not allow_container:
                continue
            if not metric_provider._metric_name.endswith('_container') and not allow_other:
                continue

            message = f"Booting {metric_provider.__class__.__name__}"
            metric_provider.start_profiling(self.__containers)
            if self._verbose_provider_boot:
                self.__notes_helper.add_note({'note': message, 'detail_name': '[NOTES]', 'timestamp': int(time.time_ns() / 1_000)})
                self.custom_sleep(10)

        print(TerminalColors.HEADER, '\nWaiting for Metric Providers to boot ...', TerminalColors.ENDC)
        self.custom_sleep(2)

        for metric_provider in self.__metric_providers:
            if metric_provider._metric_name.endswith('_container') and not allow_container:
                continue
            if not metric_provider._metric_name.endswith('_container') and not allow_other:
                continue

            stderr_read = metric_provider.get_stderr()
            print(f"Stderr check on {metric_provider.__class__.__name__}")
            if stderr_read is not None:
                raise RuntimeError(f"Stderr on {metric_provider.__class__.__name__} was NOT empty: {stderr_read}")


    def start_phase(self, phase, transition = True):
        config = GlobalConfig().config
        print(TerminalColors.HEADER, f"\nStarting phase {phase}.", TerminalColors.ENDC)

        if transition:
            # The force-sleep must go and we must actually check for the temperature baseline
            print(f"\nForce-sleeping for {config['measurement']['phase-transition-time']}s")
            self.custom_sleep(config['measurement']['phase-transition-time'])
            print(TerminalColors.HEADER, '\nChecking if temperature is back to baseline ...', TerminalColors.ENDC)

        phase_time = int(time.time_ns() / 1_000)
        self.__notes_helper.add_note({'note': f"Starting phase {phase}", 'detail_name': '[NOTES]', 'timestamp': phase_time})

        if phase in self.__phases:
            raise RuntimeError(f"'{phase}' as phase name has already used. Please set unique name for phases.")

        self.__phases[phase] = {'start': phase_time, 'name': phase}

    def end_phase(self, phase):
        phase_time = int(time.time_ns() / 1_000)

        if phase not in self.__phases:
            raise RuntimeError('Calling end_phase before start_phase. This is a developer error!')

        if phase in self.__services_to_pause_phase:
            for container_to_pause in self.__services_to_pause_phase[phase]:
                info_text = f"Pausing {container_to_pause} after phase: {phase}."
                print(info_text)
                self.__notes_helper.add_note({'note': info_text, 'detail_name': '[NOTES]', 'timestamp': phase_time})

                subprocess.run(['docker', 'pause', container_to_pause], check=True, stdout=subprocess.DEVNULL)


        self.__phases[phase]['end'] = phase_time
        self.__notes_helper.add_note({'note': f"Ending phase {phase}", 'detail_name': '[NOTES]', 'timestamp': phase_time})

    def run_flows(self):
        config = GlobalConfig().config
        # run the flows
        for el in self._usage_scenario['flow']:
            print(TerminalColors.HEADER, '\nRunning flow: ', el['name'], TerminalColors.ENDC)

            self.start_phase(el['name'].replace('[', '').replace(']',''), transition=False)

            for inner_el in el['commands']:
                if 'note' in inner_el:
                    self.__notes_helper.add_note({'note': inner_el['note'], 'detail_name': el['container'], 'timestamp': int(time.time_ns() / 1_000)})

                if inner_el['type'] == 'console':
                    print(TerminalColors.HEADER, '\nConsole command', inner_el['command'], 'on container', el['container'], TerminalColors.ENDC)

                    docker_exec_command = ['docker', 'exec']

                    docker_exec_command.append(el['container'])
                    if shell := inner_el.get('shell', False):
                        docker_exec_command.append(shell)
                        docker_exec_command.append('-c')
                        docker_exec_command.append(inner_el['command'])
                    else:
                        for cmd in inner_el['command'].split():
                            docker_exec_command.append(cmd)

                    # Note: In case of a detach wish in the usage_scenario.yml:
                    # We are NOT using the -d flag from docker exec, as this prohibits getting the stdout.
                    # Since Popen always make the process asynchronous we can leverage this to emulate a detached
                    # behavior

                    stderr_behaviour = stdout_behaviour = subprocess.DEVNULL
                    if inner_el.get('log-stdout', False):
                        stdout_behaviour = subprocess.PIPE
                    if inner_el.get('log-stderr', True):
                        stderr_behaviour = subprocess.PIPE


                    if inner_el.get('detach', False) is True:
                        print('Process should be detached. Running asynchronously and detaching ...')
                        #pylint: disable=consider-using-with
                        ps = subprocess.Popen(
                            docker_exec_command,
                            stderr=stderr_behaviour,
                            stdout=stdout_behaviour,
                            encoding='UTF-8',
                        )
                        if stderr_behaviour == subprocess.PIPE:
                            os.set_blocking(ps.stderr.fileno(), False)
                        if  stdout_behaviour == subprocess.PIPE:
                            os.set_blocking(ps.stdout.fileno(), False)

                        self.__ps_to_kill.append({'ps': ps, 'cmd': inner_el['command'], 'ps_group': False})
                    else:
                        print(f"Process should be synchronous. Alloting {config['measurement']['flow-process-runtime']}s runtime ...")
                        ps = subprocess.run(
                            docker_exec_command,
                            stderr=stderr_behaviour,
                            stdout=stdout_behaviour,
                            encoding='UTF-8',
                            check=False, # cause it will be checked later and also ignore-errors checked
                            timeout=config['measurement']['flow-process-runtime'],
                        )

                    self.__ps_to_read.append({
                        'cmd': docker_exec_command,
                        'ps': ps,
                        'container_name': el['container'],
                        'read-notes-stdout': inner_el.get('read-notes-stdout', False),
                        'ignore-errors': inner_el.get('ignore-errors', False),
                        'read-sci-stdout': inner_el.get('read-sci-stdout', False),
                        'detail_name': el['container'],
                        'detach': inner_el.get('detach', False),
                    })


                else:
                    raise RuntimeError('Unknown command type in flow: ', inner_el['type'])

                if self._debugger.active:
                    self._debugger.pause('Waiting to start next command in flow')

            self.end_phase(el['name'].replace('[', '').replace(']',''))
            self.check_process_returncodes()

    # this function should never be called twice to avoid double logging of metrics
    def stop_metric_providers(self):
        print(TerminalColors.HEADER, 'Stopping metric providers and parsing measurements', TerminalColors.ENDC)
        errors = []
        for metric_provider in self.__metric_providers:
            if not metric_provider.has_started():
                continue

            stderr_read = metric_provider.get_stderr()
            if stderr_read is not None:
                errors.append(f"Stderr on {metric_provider.__class__.__name__} was NOT empty: {stderr_read}")

            metric_provider.stop_profiling()

            df = metric_provider.read_metrics(self.__run_id, self.__containers)
            if isinstance(df, int):
                print('Imported', TerminalColors.HEADER, df, TerminalColors.ENDC, 'metrics from ', metric_provider.__class__.__name__)
                # If df returns an int the data has already been committed to the db
                continue

            print('Imported', TerminalColors.HEADER, df.shape[0], TerminalColors.ENDC, 'metrics from ', metric_provider.__class__.__name__)
            if df is None or df.shape[0] == 0:
                errors.append(f"No metrics were able to be imported from: {metric_provider.__class__.__name__}")

            f = StringIO(df.to_csv(index=False, header=False))
            DB().copy_from(file=f, table='measurements', columns=df.columns, sep=',')
        self.__metric_providers = []
        if errors:
            raise RuntimeError("\n".join(errors))


    def read_and_cleanup_processes(self):
        print(TerminalColors.HEADER, '\nReading process stdout/stderr (if selected) and cleaning them up', TerminalColors.ENDC)
        process_helpers.kill_ps(self.__ps_to_kill)
        for ps in self.__ps_to_read:
            if ps['detach']:
                stdout, stderr = ps['ps'].communicate(timeout=5)
            else:
                stdout = ps['ps'].stdout
                stderr = ps['ps'].stderr

            if stdout:
                for line in stdout.splitlines():
                    print('stdout from process:', ps['cmd'], line)
                    self.add_to_log(ps['container_name'], f"stdout: {line}", ps['cmd'])

                    if ps['read-notes-stdout']:
                        if note := self.__notes_helper.parse_note(line):
                            self.__notes_helper.add_note({'note': note[1], 'detail_name': ps['detail_name'], 'timestamp': note[0]})

                    if ps['read-sci-stdout']:
                        if match := re.findall(r'GMT_SCI_R=(\d+)', line):
                            self._sci['R'] += int(match[0])
            if stderr:
                stderr = stderr.splitlines()
                for line in stderr:
                    print('stderr from process:', ps['cmd'], line)
                    self.add_to_log(ps['container_name'], f"stderr: {line}", ps['cmd'])

    def check_process_returncodes(self):
        print(TerminalColors.HEADER, '\nChecking process return codes', TerminalColors.ENDC)
        for ps in self.__ps_to_read:
            if not ps['ignore-errors']:
                if process_helpers.check_process_failed(ps['ps'], ps['detach']):
                    stderr = 'Not read because detached. Please use stderr logging.'
                    if not ps['detach']:
                        stderr = ps['ps'].stderr
                    raise RuntimeError(f"Process '{ps['cmd']}' had bad returncode: {ps['ps'].returncode}. Stderr: {stderr}. Detached process: {ps['detach']}")

    def start_measurement(self):
        self.__start_measurement = int(time.time_ns() / 1_000)
        self.__notes_helper.add_note({'note': 'Start of measurement', 'detail_name': '[NOTES]', 'timestamp': self.__start_measurement})

    def end_measurement(self):
        self.__end_measurement = int(time.time_ns() / 1_000)
        self.__notes_helper.add_note({'note': 'End of measurement', 'detail_name': '[NOTES]', 'timestamp': self.__end_measurement})

    def update_start_and_end_times(self):
        print(TerminalColors.HEADER, '\nUpdating start and end measurement times', TerminalColors.ENDC)
        DB().query("""
            UPDATE runs
            SET start_measurement=%s, end_measurement=%s
            WHERE id = %s
            """, params=(self.__start_measurement, self.__end_measurement, self.__run_id))

    def store_phases(self):
        print(TerminalColors.HEADER, '\nUpdating phases in DB', TerminalColors.ENDC)
        # internally PostgreSQL stores JSON ordered. This means our name-indexed dict will get
        # re-ordered. Therefore we change the structure and make it a list now.
        # We did not make this before, as we needed the duplicate checking of dicts
        self.__phases = list(self.__phases.values())
        DB().query("""
            UPDATE runs
            SET phases=%s
            WHERE id = %s
            """, params=(json.dumps(self.__phases), self.__run_id))

    def read_container_logs(self):
        print(TerminalColors.HEADER, '\nCapturing container logs', TerminalColors.ENDC)
        for container_id, container_info in self.__containers.items():

            stderr_behaviour = stdout_behaviour = subprocess.DEVNULL
            if container_info['log-stdout'] is True:
                stdout_behaviour = subprocess.PIPE
            if container_info['log-stderr'] is True:
                stderr_behaviour = subprocess.PIPE


            log = subprocess.run(
                ['docker', 'logs', '-t', container_id],
                check=True,
                encoding='UTF-8',
                stdout=stdout_behaviour,
                stderr=stderr_behaviour,
            )

            if log.stdout:
                self.add_to_log(container_id, f"stdout: {log.stdout}")
                if container_info['read-sci-stdout']:
                    for line in log.stdout.splitlines():
                        if match := re.findall(r'GMT_SCI_R=(\d+)', line):
                            self._sci['R'] += int(match[0])

            if log.stderr:
                self.add_to_log(container_id, f"stderr: {log.stderr}")

    def save_stdout_logs(self):
        print(TerminalColors.HEADER, '\nSaving logs to DB', TerminalColors.ENDC)
        logs_as_str = '\n\n'.join([f"{k}:{v}" for k,v in self.__stdout_logs.items()])
        logs_as_str = logs_as_str.replace('\x00','')
        if logs_as_str:
            DB().query("""
                UPDATE runs
                SET logs=%s
                WHERE id = %s
                """, params=(logs_as_str, self.__run_id))


    def cleanup(self):
        #https://github.com/green-coding-berlin/green-metrics-tool/issues/97
        print(TerminalColors.OKCYAN, '\nStarting cleanup routine', TerminalColors.ENDC)

        print('Stopping metric providers')
        for metric_provider in self.__metric_providers:
            metric_provider.stop_profiling()

        print('Stopping containers')
        for container_id in self.__containers:
            subprocess.run(['docker', 'rm', '-f', container_id], check=True, stderr=subprocess.DEVNULL)

        print('Removing network')
        for network_name in self.__networks:
            # no check=True, as the network might already be gone. We do not want to fail here
            subprocess.run(['docker', 'network', 'rm', network_name], stderr=subprocess.DEVNULL, check=False)

        if not self._no_file_cleanup:
            print('Removing files')
            subprocess.run(['rm', '-Rf', self._tmp_folder], stderr=subprocess.DEVNULL, check=True)

        self.remove_docker_images()

        process_helpers.kill_ps(self.__ps_to_kill)
        print(TerminalColors.OKBLUE, '-Cleanup gracefully completed', TerminalColors.ENDC)

        self.__notes_helper = Notes()
        self.__containers = {}
        self.__networks = []
        self.__ps_to_kill = []
        self.__ps_to_read = []
        self.__metric_providers = []
        self.__phases = {}
        self.__start_measurement = None
        self.__end_measurement = None
        self.__join_default_network = False
        #self.__filename = self._original_filename # # we currently do not use this variable
        self.__folder = f"{self._tmp_folder}/repo"
        self.__run_id = None

    def run(self):
        '''
            The run function is just a wrapper for the intended sequential flow of a GMT run.
            Mainly designed to call the functions individually for testing, but also
            if the flow ever needs to repeat certain blocks.

            The runner is to be thought of as a state machine.

            Methods thus will behave differently given the runner was instantiated with different arguments.

        '''
        return_run_id = None
        try:
            config = GlobalConfig().config
            self.check_system('start')
            return_run_id = self.initialize_run()
            self.initialize_folder(self._tmp_folder)
            self.checkout_repository()
            self.initial_parse()
            self.import_metric_providers()
            self.populate_image_names()
            self.check_running_containers()
            self.remove_docker_images()
            self.download_dependencies()
            self.register_machine_id()
            self.update_and_insert_specs()
            if self._debugger.active:
                self._debugger.pause('Initial load complete. Waiting to start metric providers')

            self.start_metric_providers(allow_other=True, allow_container=False)
            if self._debugger.active:
                self._debugger.pause('metric-providers (non-container) start complete. Waiting to start measurement')

            self.custom_sleep(config['measurement']['idle-time-start'])

            self.start_measurement()

            self.start_phase('[BASELINE]')
            self.custom_sleep(5)
            self.end_phase('[BASELINE]')

            if self._debugger.active:
                self._debugger.pause('Network setup complete. Waiting to start container build')

            self.start_phase('[INSTALLATION]')
            self.build_docker_images()
            self.end_phase('[INSTALLATION]')

            if self._debugger.active:
                self._debugger.pause('Network setup complete. Waiting to start container boot')

            self.start_phase('[BOOT]')
            self.setup_networks()
            self.setup_services()
            self.end_phase('[BOOT]')

            if self._debugger.active:
                self._debugger.pause('Container setup complete. Waiting to start container provider boot')

            self.start_metric_providers(allow_container=True, allow_other=False)

            if self._debugger.active:
                self._debugger.pause('metric-providers (container) start complete. Waiting to start idle phase')

            self.start_phase('[IDLE]')
            self.custom_sleep(5)
            self.end_phase('[IDLE]')

            if self._debugger.active:
                self._debugger.pause('Container idle phase complete. Waiting to start flows')

            self.start_phase('[RUNTIME]')
            self.run_flows() # can trigger debug breakpoints;
            self.end_phase('[RUNTIME]')

            if self._debugger.active:
                self._debugger.pause('Container flows complete. Waiting to start remove phase')

            self.start_phase('[REMOVE]')
            self.custom_sleep(1)
            self.end_phase('[REMOVE]')

            if self._debugger.active:
                self._debugger.pause('Remove phase complete. Waiting to stop and cleanup')

            self.end_measurement()
            self.check_process_returncodes()
            self.custom_sleep(config['measurement']['idle-time-end'])
            self.store_phases()
            self.update_start_and_end_times()

        except BaseException as exc:
            self.add_to_log(exc.__class__.__name__, str(exc))
            raise exc
        finally:
            try:
                self.read_container_logs()
            except BaseException as exc:
                self.add_to_log(exc.__class__.__name__, str(exc))
                raise exc
            finally:
                try:
                    self.read_and_cleanup_processes()
                except BaseException as exc:
                    self.add_to_log(exc.__class__.__name__, str(exc))
                    raise exc
                finally:
                    try:
                        self.save_notes_runner()
                    except BaseException as exc:
                        self.add_to_log(exc.__class__.__name__, str(exc))
                        raise exc
                    finally:
                        try:
                            self.stop_metric_providers()
                        except BaseException as exc:
                            self.add_to_log(exc.__class__.__name__, str(exc))
                            raise exc
                        finally:
                            try:
                                self.save_stdout_logs()
                            except BaseException as exc:
                                self.add_to_log(exc.__class__.__name__, str(exc))
                                raise exc
                            finally:
                                self.cleanup()  # always run cleanup automatically after each run

        print(TerminalColors.OKGREEN, arrows('MEASUREMENT SUCCESSFULLY COMPLETED'), TerminalColors.ENDC)

        return return_run_id # we cannot return self.__run_id as this is reset in cleanup()

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--uri', type=str, help='The URI to get the usage_scenario.yml from. Can be either a local directory starting  with / or a remote git repository starting with http(s)://')
    parser.add_argument('--branch', type=str, help='Optionally specify the git branch when targeting a git repository')
    parser.add_argument('--name', type=str, help='A name which will be stored to the database to discern this run from others')
    parser.add_argument('--filename', type=str, default='usage_scenario.yml', help='An optional alternative filename if you do not want to use "usage_scenario.yml"')
    parser.add_argument('--config-override', type=str, help='Override the configuration file with the passed in yml file. Must be located in the same directory as the regular configuration file. Pass in only the name.')
    parser.add_argument('--no-file-cleanup', action='store_true', help='Do not delete files in /tmp/green-metrics-tool')
    parser.add_argument('--debug', action='store_true', help='Activate steppable debug mode')
    parser.add_argument('--allow-unsafe', action='store_true', help='Activate unsafe volume bindings, ports and complex environment vars')
    parser.add_argument('--skip-unsafe', action='store_true', help='Skip unsafe volume bindings, ports and complex environment vars')
    parser.add_argument('--skip-system-checks', action='store_true', help='Skip checking the system if the GMT can run')
    parser.add_argument('--verbose-provider-boot', action='store_true', help='Boot metric providers gradually')
    parser.add_argument('--full-docker-prune', action='store_true', help='Stop and remove all containers, build caches, volumes and images on the system')
    parser.add_argument('--docker-prune', action='store_true', help='Prune all unassociated build caches, networks volumes and stopped containers on the system')
    parser.add_argument('--dry-run', action='store_true', help='Removes all sleeps. Resulting measurement data will be skewed.')
    parser.add_argument('--dev-repeat-run', action='store_true', help='Checks if a docker image is already in the local cache and will then not build it. Also doesn\'t clear the images after a run')
    parser.add_argument('--print-logs', action='store_true', help='Prints the container and process logs to stdout')

    args = parser.parse_args()

    if args.uri is None:
        parser.print_help()
        error_helpers.log_error('Please supply --uri to get usage_scenario.yml from')
        sys.exit(1)

    if args.allow_unsafe and args.skip_unsafe:
        parser.print_help()
        error_helpers.log_error('--allow-unsafe and skip--unsafe in conjuction is not possible')
        sys.exit(1)

    if args.dev_repeat_run and (args.docker_prune or args.full_docker_prune):
        parser.print_help()
        error_helpers.log_error('--dev-repeat-run blocks pruning docker images. Combination is not allowed')
        sys.exit(1)

    if args.full_docker_prune and GlobalConfig().config['postgresql']['host'] == 'green-coding-postgres-container':
        parser.print_help()
        error_helpers.log_error('--full-docker-prune is set while your database host is "green-coding-postgres-container".\nThe switch is only for remote measuring machines. It would stop the GMT images itself when running locally')
        sys.exit(1)

    if args.name is None:
        parser.print_help()
        error_helpers.log_error('Please supply --name')
        sys.exit(1)

    if args.uri[0:8] == 'https://' or args.uri[0:7] == 'http://':
        print('Detected supplied URL: ', args.uri)
        run_type = 'URL'
    elif args.uri[0:1] == '/':
        print('Detected supplied folder: ', args.uri)
        run_type = 'folder'
        if not Path(args.uri).is_dir():
            parser.print_help()
            error_helpers.log_error('Could not find folder on local system. Please double check: ', args.uri)
            sys.exit(1)
    else:
        parser.print_help()
        error_helpers.log_error('Could not detected correct URI. Please use local folder in Linux format /folder/subfolder/... or URL http(s):// : ', args.uri)
        sys.exit(1)

    if args.config_override is not None:
        if args.config_override[-4:] != '.yml':
            parser.print_help()
            error_helpers.log_error('Config override file must be a yml file')
            sys.exit(1)
        if not Path(f"{CURRENT_DIR}/{args.config_override}").is_file():
            parser.print_help()
            error_helpers.log_error(f"Could not find config override file on local system. Please double check: {CURRENT_DIR}/{args.config_override}")
            sys.exit(1)
        GlobalConfig(config_name=args.config_override)

    successful_run_id = None
    runner = Runner(name=args.name, uri=args.uri, uri_type=run_type, filename=args.filename,
                    branch=args.branch, debug_mode=args.debug, allow_unsafe=args.allow_unsafe,
                    no_file_cleanup=args.no_file_cleanup, skip_system_checks=args.skip_system_checks,
                    skip_unsafe=args.skip_unsafe,verbose_provider_boot=args.verbose_provider_boot,
                    full_docker_prune=args.full_docker_prune, dry_run=args.dry_run,
                    dev_repeat_run=args.dev_repeat_run, docker_prune=args.docker_prune)

    # Using a very broad exception makes sense in this case as we have excepted all the specific ones before
    #pylint: disable=broad-except
    try:
        successful_run_id = runner.run()  # Start main code

        # this code should live at a different position.
        # From a user perspective it makes perfect sense to run both jobs directly after each other
        # In a cloud setup it however makes sense to free the measurement machine as soon as possible
        # So this code should be individually callable, separate from the runner

        print(TerminalColors.HEADER, '\nCalculating and storing phases data. This can take a couple of seconds ...', TerminalColors.ENDC)

        # get all the metrics from the measurements table grouped by metric
        # loop over them issueing separate queries to the DB
        from tools.phase_stats import build_and_store_phase_stats

        print("Run id is", successful_run_id)
        build_and_store_phase_stats(successful_run_id, runner._sci)


        print(TerminalColors.OKGREEN,'\n\n####################################################################################')
        print(f"Please access your report on the URL {GlobalConfig().config['cluster']['metrics_url']}/stats.html?id={successful_run_id}")
        print('####################################################################################\n\n', TerminalColors.ENDC)

    except FileNotFoundError as e:
        error_helpers.log_error('Docker command failed.', e, successful_run_id)
    except subprocess.CalledProcessError as e:
        error_helpers.log_error('Docker command failed', 'Stdout:', e.stdout, 'Stderr:', e.stderr, successful_run_id)
    except KeyError as e:
        error_helpers.log_error('Was expecting a value inside the usage_scenario.yml file, but value was missing: ', e, successful_run_id)
    except RuntimeError as e:
        error_helpers.log_error('RuntimeError occured in runner.py: ', e, successful_run_id)
    except BaseException as e:
        error_helpers.log_error('Base exception occured in runner.py: ', e, successful_run_id)
    finally:
        if args.print_logs: print("Container logs:", runner.get_logs())
