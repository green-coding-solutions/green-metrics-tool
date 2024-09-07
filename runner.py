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
from html import escape
import sys
import importlib
import re
from io import StringIO
from pathlib import Path
import random
import shutil
import yaml
from collections import OrderedDict
from datetime import datetime

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib import utils
from lib import process_helpers
from lib import hardware_info
from lib import hardware_info_root
from lib import error_helpers
from lib.repo_info import get_repo_info
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

class Runner:
    def __init__(self,
        *, uri, uri_type, name=None, filename='usage_scenario.yml', branch=None,
        debug_mode=False, allow_unsafe=False,  skip_system_checks=False,
        skip_unsafe=False, verbose_provider_boot=False, full_docker_prune=False,
        dev_no_sleeps=False, dev_no_build=False, dev_no_metrics=False,
        dev_flow_timetravel=False, dev_no_optimizations=False, docker_prune=False, job_id=None):

        if skip_unsafe is True and allow_unsafe is True:
            raise RuntimeError('Cannot specify both --skip-unsafe and --allow-unsafe')

        # variables that should not change if you call run multiple times
        if name:
            self._name = name
        else:
            self._name = f"Run {datetime.now()}"
        self._debugger = DebugHelper(debug_mode)
        self._allow_unsafe = allow_unsafe
        self._skip_unsafe = skip_unsafe
        self._skip_system_checks = skip_system_checks
        self._verbose_provider_boot = verbose_provider_boot
        self._full_docker_prune = full_docker_prune
        self._docker_prune = docker_prune
        self._dev_no_sleeps = dev_no_sleeps
        self._dev_no_build = dev_no_build
        self._dev_no_metrics = dev_no_metrics
        self._dev_flow_timetravel = dev_flow_timetravel
        self._dev_no_optimizations = dev_no_optimizations
        self._uri = uri
        self._uri_type = uri_type
        self._original_filename = filename
        self._branch = branch
        self._tmp_folder = Path('/tmp/green-metrics-tool').resolve() # since linux has /tmp and macos /private/tmp
        self._usage_scenario = {}
        self._architecture = utils.get_architecture()
        self._sci = {'R_d': None, 'R': 0}
        self._job_id = job_id
        self._arguments = locals()
        self._repo_folder = f"{self._tmp_folder}/repo" # default if not changed in checkout_repository
        self._run_id = None
        self._commit_hash = None
        self._commit_timestamp = None

        del self._arguments['self'] # self is not needed and also cannot be serialzed. We remove it


        # transient variables that are created by the runner itself
        # these are accessed and processed on cleanup and then reset
        # They are __ as they should not be changed because this could break the state of the runner
        self.__stdout_logs = OrderedDict()
        self.__containers = {}
        self.__networks = []
        self.__ps_to_kill = []
        self.__ps_to_read = []
        self.__metric_providers = []
        self.__notes_helper = Notes()
        self.__phases = OrderedDict()
        self.__start_measurement_seconds = None
        self.__start_measurement = None
        self.__end_measurement = None
        self.__services_to_pause_phase = {}
        self.__join_default_network = False
        self.__docker_params = []
        self.__working_folder = self._repo_folder
        self.__working_folder_rel = ''

        # we currently do not use this variable
        # self.__filename = self._original_filename # this can be changed later if working directory changes

    def custom_sleep(self, sleep_time):
        if not self._dev_no_sleeps:
            print(TerminalColors.HEADER, '\nSleeping for : ', sleep_time, TerminalColors.ENDC)
            time.sleep(sleep_time)

    def initialize_run(self):
        # We issue a fetch_one() instead of a query() here, cause we want to get the RUN_ID

        # we also update the branch here again, as this might not be main in case of local filesystem
        self._run_id = DB().fetch_one("""
                INSERT INTO runs (job_id, name, uri, email, branch, filename, commit_hash, commit_timestamp, runner_arguments, created_at)
                VALUES (%s, %s, %s, 'manual', %s, %s, %s, %s, %s, NOW())
                RETURNING id
                """, params=(self._job_id, self._name, self._uri, self._branch, self._original_filename, self._commit_hash, self._commit_timestamp, json.dumps(self._arguments)))[0]
        return self._run_id

    def get_optimizations_ignore(self):
        return self._usage_scenario.get('optimizations_ignore', [])

    # This function takes a path and a file and joins them while making sure that no one is trying to escape the
    # path with `..`, symbolic links or similar.
    # We always return the same error message including the path and file parameter, never `filename` as
    # otherwise we might disclose if certain files exist or not.
    def join_paths(self, path, path2, force_path_as_root=False):
        filename = os.path.realpath(os.path.join(path, path2))

        # If the original path is a symlink we need to resolve it.
        path = os.path.realpath(path)

        # This is a special case in which the file is '.'
        if filename == path.rstrip('/'):
            return filename

        if not filename.startswith(self._repo_folder):
            raise ValueError(f"{path2} must not be in folder above root repo folder {self._repo_folder}")

        if force_path_as_root and not filename.startswith(path):
            raise RuntimeError(f"{path2} must not be in folder above {path}")

        # Another way to implement this. This is checking again but we want to be extra secure 👾
        if Path(self._repo_folder).resolve(strict=True) not in Path(path, path2).resolve(strict=True).parents:
            raise ValueError(f"{path2} must not be in folder above root repo folder {self._repo_folder}")

        if force_path_as_root and Path(path).resolve(strict=True) not in Path(path, path2).resolve(strict=True).parents:
            raise ValueError(f"{path2} must not be in folder above {path}")


        if os.path.exists(filename):
            return filename

        raise FileNotFoundError(f"{path2} in {path} not found")



    def initialize_folder(self, path):
        shutil.rmtree(path, ignore_errors=True)
        Path(path).mkdir(parents=True, exist_ok=True)

    def save_notes_runner(self):
        print(TerminalColors.HEADER, '\nSaving notes: ', TerminalColors.ENDC, self.__notes_helper.get_notes())
        self.__notes_helper.save_to_db(self._run_id)

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
                        self._repo_folder
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
                        self._repo_folder
                    ],
                    check=True,
                    capture_output=True,
                    encoding='UTF-8'
                )  # always name target-dir repo according to spec

        else:
            if self._branch:
                # we never want to checkout a local directory to a different branch as this might also be the GMT directory itself and might confuse the tool
                raise RuntimeError('Specified --branch but using local URI. Did you mean to specify a github url?')
            # If the provided uri is a symlink we need to resolve it.
            path = os.path.realpath(self._uri)
            self.__working_folder = self._repo_folder = path

        self._branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=self._repo_folder, encoding='UTF-8').strip()

        git_repo_root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=self._repo_folder, encoding='UTF-8').strip()
        if git_repo_root != self._repo_folder:
            raise RuntimeError('Supplied folder through --uri is not the root of the git repository. Please only supply the root folder and then the target directory through --filename')

        # we can safely do this, even with problematic folders, as the folder can only be a local unsafe one when
        # running in CLI mode
        self._commit_hash, self._commit_timestamp = get_repo_info(self._repo_folder)

    # This method loads the yml file and takes care that the includes work and are secure.
    # It uses the tagging infrastructure provided by https://pyyaml.org/wiki/PyYAMLDocumentation
    # Inspiration from https://github.com/tanbro/pyyaml-include which we can't use as it doesn't
    # do security checking and has no option to select when imported
    def load_yml_file(self):
        #pylint: disable=too-many-ancestors
        runner_join_paths = self.join_paths
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

                try:
                    filename = runner_join_paths(self._root, nodes[0], force_path_as_root=True)
                except RuntimeError as exc:
                    raise ValueError(f"Included compose file \"{nodes[0]}\" may only be in the same directory as the usage_scenario file as otherwise relative context_paths and volume_paths cannot be mapped anymore") from exc

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

        usage_scenario_file = self.join_paths(self._repo_folder, self._original_filename)

        # We set the working folder now to the actual location of the usage_scenario
        if '/' in self._original_filename:
            self.__working_folder_rel = self._original_filename.rsplit('/', 1)[0]
            self.__working_folder = usage_scenario_file.rsplit('/', 1)[0]
            #self.__filename = usage_scenario_file.rsplit('/', 1)[1] # we currently do not use this variable
            print("Working folder changed to ", self.__working_folder)


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
            for key in [sname for sname, content in yml_obj.get('services', {}).items() if content is None]:
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

    def prepare_docker(self):
        # Disable Docker CLI hints (e.g. "What's Next? ...")
        os.environ['DOCKER_CLI_HINTS'] = 'false'

    def check_running_containers(self):
        result = subprocess.run(['docker', 'ps' ,'--format', '{{.Names}}'],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                check=True, encoding='UTF-8')
        for line in result.stdout.splitlines():
            for running_container in line.split(','): # if docker container has multiple tags, they will be split by comma, so we only want to
                for service_name in self._usage_scenario.get('services', {}):
                    if 'container_name' in self._usage_scenario['services'][service_name]:
                        container_name = self._usage_scenario['services'][service_name]['container_name']
                    else:
                        container_name = service_name

                    if running_container == container_name:
                        raise PermissionError(f"Container '{container_name}' is already running on system. Please close it before running the tool.")

    def populate_image_names(self):
        for service_name, service in self._usage_scenario.get('services', {}).items():
            if not service.get('image', None): # image is a non-mandatory field. But we need it, so we tmp it
                if self._dev_no_build:
                    service['image'] = f"{service_name}"
                else:
                    service['image'] = f"{service_name}_{random.randint(500000,10000000)}"

    def remove_docker_images(self):
        if self._dev_no_build:
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

        gmt_hash, _ = get_repo_info(CURRENT_DIR)

        # There are two ways we get hardware info. First things we don't need to be root to do which we get through
        # a method call. And then things we need root privilege which we need to call as a subprocess with sudo. The
        # install.sh script should have added the script to the sudoes file.
        machine_specs = hardware_info.get_default_values()

        if len(hardware_info_root.get_root_list()) > 0:
            ps = subprocess.run(['sudo', '/usr/bin/python3', '-m', 'lib.hardware_info_root'], stdout=subprocess.PIPE, cwd=CURRENT_DIR, check=True, encoding='UTF-8')
            machine_specs_root = json.loads(ps.stdout)
            machine_specs.update(machine_specs_root)

        keys = ["measurement", "sci"]
        measurement_config = {key: config.get(key, None) for key in keys}

        # Insert auxilary info for the run. Not critical.
        DB().query("""
            UPDATE runs
            SET
                machine_id=%s, machine_specs=%s, measurement_config=%s,
                usage_scenario = %s, gmt_hash=%s
            WHERE id = %s
            """, params=(
            config['machine']['id'],
            escape(json.dumps(machine_specs), quote=False),
            json.dumps(measurement_config),
            escape(json.dumps(self._usage_scenario), quote=False),
            gmt_hash,
            self._run_id)
        )

    def import_metric_providers(self):
        if self._dev_no_metrics:
            print(TerminalColors.HEADER, '\nSkipping import of metric providers', TerminalColors.ENDC)
            return

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

            if self._skip_system_checks:
                conf['skip_check'] = True

            print(f"Importing {class_name} from {module_path}")
            print(f"Configuration is {conf}")

            module = importlib.import_module(module_path)

            metric_provider_obj = getattr(module, class_name)(**conf)

            self.__metric_providers.append(metric_provider_obj)

            if hasattr(metric_provider_obj, 'get_docker_params'):
                services_list = ",".join(list(self._usage_scenario.get('services', {}).keys()))
                self.__docker_params += metric_provider_obj.get_docker_params(no_proxy_list=services_list)


        self.__metric_providers.sort(key=lambda item: 'rapl' not in item.__class__.__name__.lower())

    def download_dependencies(self):
        if self._dev_no_build:
            print(TerminalColors.HEADER, '\nSkipping downloading dependencies', TerminalColors.ENDC)
            return

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
        # only lowercase letters are allowed for tags
        name = name.lower()
        name = f"{name}_gmt_run_tmp"
        return name

    def build_docker_images(self):
        config = GlobalConfig().config
        print(TerminalColors.HEADER, '\nBuilding Docker images', TerminalColors.ENDC)

        # Create directory /tmp/green-metrics-tool/docker_images
        temp_dir = f"{self._tmp_folder}/docker_images"
        self.initialize_folder(temp_dir)

        # technically the usage_scenario needs no services and can also operate on an empty list
        # This use case is when you have running containers on your host and want to benchmark some code running in them
        for _, service in self._usage_scenario.get('services', {}).items():
            # minimal protection from possible shell escapes.
            # since we use subprocess without shell we should be safe though
            if re.findall(r'(\.\.|\$|\'|"|`|!)', service['image']):
                raise ValueError(f"In scenario file the builds contains an invalid image name: {service['image']}")

            tmp_img_name = self.clean_image_name(service['image'])

            # If we are in developer repeat runs check if the docker image has already been built
            try:
                subprocess.run(['docker', 'inspect', '--type=image', tmp_img_name],
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE,
                                         encoding='UTF-8',
                                         check=True)
                # The image exists so exit and don't build
                print(f"Image {service['image']} exists in build cache. Skipping build ...")
                continue
            except subprocess.CalledProcessError:
                pass

            if 'build' in service:
                context, dockerfile = self.get_build_info(service)
                print(f"Building {service['image']}")
                self.__notes_helper.add_note({'note': f"Building {service['image']}", 'detail_name': '[NOTES]', 'timestamp': int(time.time_ns() / 1_000)})

                # Make sure the context docker file exists and is not trying to escape some root. We don't need the returns
                context_path = self.join_paths(self.__working_folder, context)
                self.join_paths(context_path, dockerfile)

                docker_build_command = ['docker', 'run', '--rm',
                    '-v', '/workspace',
                    '-v', f"{self._repo_folder}:/tmp/repo:ro", # this is the folder where the usage_scenario is!
                    '-v', f"{temp_dir}:/output",
                    'gcr.io/kaniko-project/executor:latest',
                    f"--dockerfile=/tmp/repo/{self.__working_folder_rel}/{context}/{dockerfile}",
                    '--context', f'dir:///tmp/repo/{self.__working_folder_rel}/{context}',
                    f"--destination={tmp_img_name}",
                    f"--tar-path=/output/{tmp_img_name}.tar",
                    '--cleanup=true',
                    '--no-push']

                if self.__docker_params:
                    docker_build_command[2:2] = self.__docker_params

                print(' '.join(docker_build_command))

                ps = subprocess.run(docker_build_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='UTF-8', timeout=config['measurement']['total-duration'], check=False)

                if ps.returncode != 0:
                    print(f"Error: {ps.stderr} \n {ps.stdout}")
                    raise OSError(f"Docker build failed\nStderr: {ps.stderr}\nStdout: {ps.stdout}")

                # import the docker image locally
                image_import_command = ['docker', 'load', '-q', '-i', f"{temp_dir}/{tmp_img_name}.tar"]
                print(' '.join(image_import_command))
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
                    if __name__ == '__main__':
                        print(TerminalColors.OKCYAN, '\nThe docker image could not be pulled. Since you are working locally we can try looking in your local images. Do you want that? (y/N).', TerminalColors.ENDC)
                        if sys.stdin.readline().strip().lower() == 'y':
                            try:
                                subprocess.run(['docker', 'inspect', '--type=image', service['image']],
                                                         stdout=subprocess.PIPE,
                                                         stderr=subprocess.PIPE,
                                                         encoding='UTF-8',
                                                         check=True)
                                print('Docker image found locally. Tagging now for use in cached runs ...')
                            except subprocess.CalledProcessError:
                                raise OSError(f"Docker pull failed and image does not exist locally. Is your image name correct and are you connected to the internet: {service['image']}") from subprocess.CalledProcessError
                        else:
                            raise OSError(f"Docker pull failed. Is your image name correct and are you connected to the internet: {service['image']}")
                    else:
                        raise OSError(f"Docker pull failed. Is your image name correct and are you connected to the internet: {service['image']}")

                # tagging must be done in pull and local case, so we can get the correct container later
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

    def order_services(self, services):
        names_ordered = []
        def order_service_names(service_name, visited=None):
            if visited is None:
                visited = set()
            if service_name in visited:
                raise RuntimeError(f"Cycle found in depends_on definition with service '{service_name}'!")
            visited.add(service_name)

            if service_name not in services:
                raise RuntimeError(f"Dependent service '{service_name}' defined in 'depends_on' does not exist in usage_scenario!")

            service = services[service_name]
            if 'depends_on' in service:
                for dep in service['depends_on']:
                    if dep not in names_ordered:
                        order_service_names(dep, visited)

            if service_name not in names_ordered:
                names_ordered.append(service_name)

        # Iterate over all services and sort them with the recursive function 'order_service_names'
        for service_name in services.keys():
            order_service_names(service_name)
        print("Startup order: ", names_ordered)
        return OrderedDict((key, services[key]) for key in names_ordered)

    def setup_services(self):
        config = GlobalConfig().config
        print(TerminalColors.HEADER, '\nSetting up services', TerminalColors.ENDC)
        # technically the usage_scenario needs no services and can also operate on an empty list
        # This use case is when you have running containers on your host and want to benchmark some code running in them
        services = self._usage_scenario.get('services', {})

        # Check if there are service dependencies defined with 'depends_on'.
        # If so, change the order of the services accordingly.
        services_ordered = self.order_services(services)
        known_container_names = []
        for service_name, service in services_ordered.items():

            if 'container_name' in service:
                container_name = service['container_name']
            else:
                container_name = service_name

            if container_name in known_container_names:
                raise RuntimeError(f"Container name '{container_name}' was already assigned. Please choose unique container names.")

            known_container_names.append(container_name)

            print(TerminalColors.HEADER, '\nSetting up container for service:', service_name, TerminalColors.ENDC)
            print('Container name:', container_name)

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
                docker_run_string.append(f"{self._repo_folder}:{service['folder-destination']}:ro")
            else:
                docker_run_string.append(f"{self._repo_folder}:/tmp/repo:ro")

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
                            path = os.path.realpath(os.path.join(self.__working_folder, vol[0]))
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
                        try:
                            path = self.join_paths(self.__working_folder, vol[0])
                        except FileNotFoundError as exc:
                            raise RuntimeError(f"The volume {vol[0]} could not be loaded or found at the specified path.") from exc
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
                        docker_run_string.append(str(ports)) # Ports can also be an int according to schema checker, but needs to be a string when we use subprocess
                elif self._skip_unsafe:
                    print(TerminalColors.WARNING, arrows('Found ports entry but not running in unsafe mode. Skipping'), TerminalColors.ENDC)
                else:
                    raise RuntimeError('Found "ports" but neither --skip-unsafe nor --allow-unsafe is set')

            if 'environment' in service:
                env_var_check_errors = []
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

                    # Check the key of the environment var
                    if not self._allow_unsafe and re.search(r'^[A-Z_]+[A-Z0-9_]*$', env_key) is None:
                        if self._skip_unsafe:
                            warn_message= arrows(f"Found environment var key with wrong format. Only ^[A-Z_]+[A-Z0-9_]*$ allowed: {env_key} - Skipping")
                            print(TerminalColors.WARNING, warn_message, TerminalColors.ENDC)
                            continue
                        env_var_check_errors.append(f"- key '{env_key}' has wrong format. Only ^[A-Z_]+[A-Z0-9_]*$ is allowed - Maybe consider using --allow-unsafe or --skip-unsafe")

                    # Check the value of the environment var
                    # We only forbid long values (>1024), every character is allowed.
                    # The value is directly passed to the container and is not evaluated on the host system, so there is no security related reason to forbid special characters.
                    if not self._allow_unsafe and len(env_value) > 1024:
                        if self._skip_unsafe:
                            print(TerminalColors.WARNING, arrows(f"Found environment var value with size {len(env_value)} (max allowed length is 1024) - Skipping env var '{env_key}'"), TerminalColors.ENDC)
                            continue
                        env_var_check_errors.append(f"- value of environment var '{env_key}' is too long {len(env_value)} (max allowed length is 1024) - Maybe consider using --allow-unsafe or --skip-unsafe")

                    docker_run_string.append('-e')
                    docker_run_string.append(f"{env_key}={env_value}")

                if env_var_check_errors:
                    raise RuntimeError('Docker container environment setup has problems:\n\n'.join(env_var_check_errors))

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

            if 'deploy' in service:
                if memory := service['deploy'].get('resources', {}).get('limits', {}).get('memory', None):
                    docker_run_string.append('--memory') # value in bytes
                    docker_run_string.append(str(memory))
                if cpus := service['deploy'].get('resources', {}).get('limits', {}).get('cpus', None):
                    docker_run_string.append('--cpus') # value in cores
                    docker_run_string.append(str(cpus))


            if 'healthcheck' in service:  # must come last
                if 'disable' in service['healthcheck'] and service['healthcheck']['disable'] is True:
                    docker_run_string.append('--no-healthcheck')
                else:
                    if 'test' in service['healthcheck']:
                        docker_run_string.append('--health-cmd')
                        health_string = service['healthcheck']['test']
                        if isinstance(service['healthcheck']['test'], list):
                            health_string_copy = service['healthcheck']['test'].copy()
                            health_string_command = health_string_copy.pop(0)
                            if health_string_command not in ['CMD', 'CMD-SHELL']:
                                raise RuntimeError(f"Healthcheck starts with {health_string_command}. Please use 'CMD' or 'CMD-SHELL' when supplying as list. For disabling do not use 'NONE' but the disable argument.")
                            health_string = ' '.join(health_string_copy)
                        docker_run_string.append(health_string)
                    if 'interval' in service['healthcheck']:
                        docker_run_string.append('--health-interval')
                        docker_run_string.append(service['healthcheck']['interval'])
                    if 'timeout' in service['healthcheck']:
                        docker_run_string.append('--health-timeout')
                        docker_run_string.append(service['healthcheck']['timeout'])
                    if 'retries' in service['healthcheck']:
                        docker_run_string.append('--health-retries')
                        docker_run_string.append(str(service['healthcheck']['retries'])) # we need a str to pass to subprocess
                    if 'start_period' in service['healthcheck']:
                        docker_run_string.append('--health-start-period')
                        docker_run_string.append(service['healthcheck']['start_period'])
                    if 'start_interval' in service['healthcheck']:
                        docker_run_string.append('--health-start-interval')
                        docker_run_string.append(service['healthcheck']['start_interval'])


            docker_run_string.append(self.clean_image_name(service['image']))

            # Before finally starting the container for the current service, check if the dependent services are ready.
            # If not, wait for some time. If a dependent service is not ready after a certain time, throw an error.
            # If a healthcheck is defined, the container of the dependent service must become "healthy".
            # If no healthcheck is defined, the container state "running" is sufficient.
            if 'depends_on' in service:
                for dependent_service in service['depends_on']:
                    dependent_container_name = dependent_service
                    if 'container_name' in services[dependent_service]:
                        dependent_container_name = services[dependent_service]["container_name"]

                    time_waited = 0
                    state = ''
                    health = 'healthy' # default because some containers have no health
                    max_waiting_time = config['measurement']['boot']['wait_time_dependencies']
                    while time_waited < max_waiting_time:
                        status_output = subprocess.check_output(
                            ["docker", "container", "inspect", "-f", "{{.State.Status}}", dependent_container_name],
                            stderr=subprocess.STDOUT,
                            encoding='UTF-8',
                        )
                        state = status_output.strip()
                        if time_waited == 0 or state != "running":
                            print(f"Container state of dependent service '{dependent_service}': {state}")

                        if isinstance(service['depends_on'], dict) \
                            and 'condition' in service['depends_on'][dependent_service]:

                            condition = service['depends_on'][dependent_service]['condition']
                            if condition == 'service_healthy':
                                ps = subprocess.run(
                                    ["docker", "container", "inspect", "-f", "{{.State.Health.Status}}", dependent_container_name],
                                    check=False,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, # put both in one stream
                                    encoding='UTF-8'
                                )
                                health = ps.stdout.strip()
                                print(f"Container health of dependent service '{dependent_service}': {health}")

                                if ps.returncode != 0 or health == '<nil>':
                                    raise RuntimeError(f"Health check for service '{dependent_service}' was requested by '{service_name}', but service has no healthcheck implemented! (Output was: {health})")
                                if health == 'unhealthy':
                                    raise RuntimeError(f'Health check of container "{dependent_container_name}" failed terminally with status "unhealthy" after {time_waited}s')
                            elif condition == 'service_started':
                                pass
                            else:
                                raise RuntimeError(f"Unsupported condition in healthcheck for service '{service_name}': {condition}")

                        if state == 'running' and health == 'healthy':
                            break

                        time.sleep(1)
                        time_waited += 1

                    if state != 'running':
                        raise RuntimeError(f"State check of dependent services of '{service_name}' failed! Container '{dependent_container_name}' is not running but '{state}' after waiting for {time_waited} sec! Consider checking your service configuration, the entrypoint of the container or the logs of the container.")
                    if health != 'healthy':
                        raise RuntimeError(f"Health check of dependent services of '{service_name}' failed! Container '{dependent_container_name}' is not healthy but '{health}' after waiting for {time_waited} sec! Consider checking your service configuration, the entrypoint of the container or the logs of the container.")

            if 'command' in service:  # must come last
                for cmd in service['command'].split():
                    docker_run_string.append(cmd)

            print(f"Running docker run with: {' '.join(docker_run_string)}")

            # docker_run_string must stay as list, cause this forces items to be quoted and escaped and prevents
            # injection of unwanted params

            ps = subprocess.run(
                docker_run_string,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='UTF-8'
            )

            if ps.returncode != 0:
                print(f"Error: {ps.stderr} \n {ps.stdout}")
                raise OSError(f"Docker run failed\nStderr: {ps.stderr}\nStdout: {ps.stdout}")

            container_id = ps.stdout.strip()
            self.__containers[container_id] = {
                'name': container_name,
                'log-stdout': service.get('log-stdout', False),
                'log-stderr': service.get('log-stderr', True),
                'read-notes-stdout': service.get('read-notes-stdout', False),
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

        print(TerminalColors.HEADER, '\nCurrent known containers: ', self.__containers, TerminalColors.ENDC)

    # This method only exists to make logs read-only available outside of the self context
    # Internally we are still using normal __stdout_logs access to read and not funnel through this method
    def get_logs(self):
        return self.__stdout_logs

    def add_to_log(self, container_name, message, cmd=''):
        log_entry_name = f"{container_name}_{cmd}"
        if log_entry_name not in self.__stdout_logs:
            self.__stdout_logs[log_entry_name] = ''
        self.__stdout_logs[log_entry_name] = '\n'.join((self.__stdout_logs[log_entry_name], message))


    def start_metric_providers(self, allow_container=True, allow_other=True):
        if self._dev_no_metrics:
            return

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
        # if this is omitted the stderr can be empty even if the process is not found by the OS ... python process spawning is slow ...
        self.custom_sleep(2)

        for metric_provider in self.__metric_providers:
            if metric_provider._metric_name.endswith('_container') and not allow_container:
                continue
            if not metric_provider._metric_name.endswith('_container') and not allow_other:
                continue

            stderr_read = metric_provider.get_stderr()
            print(f"Stderr check on {metric_provider.__class__.__name__}")

            if stderr_read:
                raise RuntimeError(f"Stderr on {metric_provider.__class__.__name__} was NOT empty: {stderr_read}")

    def check_total_runtime_exceeded(self):
        config = GlobalConfig().config
        if (time.time() - self.__start_measurement_seconds) > config['measurement']['total-duration']:
            raise TimeoutError(f"Timeout of {config['measurement']['total-duration']} s was exceeded. This can be configured in 'total-duration'.")

    def start_phase(self, phase, transition = True):
        config = GlobalConfig().config
        print(TerminalColors.HEADER, f"\nStarting phase {phase}.", TerminalColors.ENDC)

        self.check_total_runtime_exceeded()

        if transition:
            # The force-sleep must go and we must actually check for the temperature baseline
            print(f"\nForce-sleeping for {config['measurement']['phase-transition-time']}s")
            self.custom_sleep(config['measurement']['phase-transition-time'])
            #print(TerminalColors.HEADER, '\nChecking if temperature is back to baseline ...', TerminalColors.ENDC)

        phase_time = int(time.time_ns() / 1_000)
        self.__notes_helper.add_note({'note': f"Starting phase {phase}", 'detail_name': '[NOTES]', 'timestamp': phase_time})

        if phase in self.__phases:
            raise RuntimeError(f"'{phase}' as phase name has already used. Please set unique name for phases.")

        self.__phases[phase] = {'start': phase_time, 'name': phase}

    def end_phase(self, phase):

        self.check_total_runtime_exceeded()

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
        ps_to_kill_tmp = []
        ps_to_read_tmp = []
        exception_occured = False
        flow_id = 0
        flows_len = len(self._usage_scenario['flow'])
        while flow_id < flows_len:
            flow = self._usage_scenario['flow'][flow_id]
            ps_to_kill_tmp.clear()
            ps_to_read_tmp.clear()
            exception_occured = False # reset

            print(TerminalColors.HEADER, '\nRunning flow: ', flow['name'], TerminalColors.ENDC)

            try:
                self.start_phase(flow['name'].replace('[', '').replace(']',''), transition=False)

                for cmd_obj in flow['commands']:
                    self.check_total_runtime_exceeded()

                    if 'note' in cmd_obj:
                        self.__notes_helper.add_note({'note': cmd_obj['note'], 'detail_name': flow['container'], 'timestamp': int(time.time_ns() / 1_000)})

                    if cmd_obj['type'] == 'console':
                        print(TerminalColors.HEADER, '\nConsole command', cmd_obj['command'], 'on container', flow['container'], TerminalColors.ENDC)

                        docker_exec_command = ['docker', 'exec']

                        docker_exec_command.append(flow['container'])
                        if shell := cmd_obj.get('shell', False):
                            docker_exec_command.append(shell)
                            docker_exec_command.append('-c')
                            docker_exec_command.append(cmd_obj['command'])
                        else:
                            for cmd in cmd_obj['command'].split():
                                docker_exec_command.append(cmd)

                        # Note: In case of a detach wish in the usage_scenario.yml:
                        # We are NOT using the -d flag from docker exec, as this prohibits getting the stdout.
                        # Since Popen always make the process asynchronous we can leverage this to emulate a detached
                        # behavior

                        stderr_behaviour = stdout_behaviour = subprocess.DEVNULL
                        if cmd_obj.get('log-stdout', False):
                            stdout_behaviour = subprocess.PIPE
                        if cmd_obj.get('log-stderr', True):
                            stderr_behaviour = subprocess.PIPE


                        if cmd_obj.get('detach', False) is True:
                            print('Process should be detached. Running asynchronously and detaching ...')
                            #pylint: disable=consider-using-with,subprocess-popen-preexec-fn
                            ps = subprocess.Popen(
                                docker_exec_command,
                                stderr=stderr_behaviour,
                                stdout=stdout_behaviour,
                                preexec_fn=os.setsid,
                                encoding='UTF-8',
                            )
                            if stderr_behaviour == subprocess.PIPE:
                                os.set_blocking(ps.stderr.fileno(), False)
                            if  stdout_behaviour == subprocess.PIPE:
                                os.set_blocking(ps.stdout.fileno(), False)

                            ps_to_kill_tmp.append({'ps': ps, 'cmd': cmd_obj['command'], 'ps_group': False})
                        else:
                            print(f"Process should be synchronous. Alloting {config['measurement']['flow-process-duration']}s runtime ...")
                            ps = subprocess.run(
                                docker_exec_command,
                                stderr=stderr_behaviour,
                                stdout=stdout_behaviour,
                                encoding='UTF-8',
                                check=False, # cause it will be checked later and also ignore-errors checked
                                timeout=config['measurement']['flow-process-duration'],
                            )

                        ps_to_read_tmp.append({
                            'cmd': docker_exec_command,
                            'ps': ps,
                            'container_name': flow['container'],
                            'read-notes-stdout': cmd_obj.get('read-notes-stdout', False),
                            'ignore-errors': cmd_obj.get('ignore-errors', False),
                            'read-sci-stdout': cmd_obj.get('read-sci-stdout', False),
                            'detail_name': flow['container'],
                            'detach': cmd_obj.get('detach', False),
                        })


                    else:
                        raise RuntimeError('Unknown command type in flow: ', cmd_obj['type'])

                    if self._debugger.active:
                        self._debugger.pause('Waiting to start next command in flow')

                self.end_phase(flow['name'].replace('[', '').replace(']',''))
                self.__ps_to_kill += ps_to_kill_tmp
                self.__ps_to_read += ps_to_read_tmp # will otherwise be discarded, bc they confuse execption handling
                self.check_process_returncodes()
                flow_id += 1

            # pylint: disable=broad-exception-caught
            except BaseException as flow_exc:
                if not self._dev_flow_timetravel: # Exception handling only if explicitely wanted
                    raise flow_exc
                print('Exception occured: ', flow_exc)
                exception_occured = True


            if not self._dev_flow_timetravel: # Timetravel only if active
                continue

            print(TerminalColors.OKCYAN, '\nTime-Travel mode is active!\nWhat do you want to do?\n')
            if not exception_occured:
                print('0 -- Continue')
            print('1 -- Restart current flow\n2 -- Restart all flows\n3 -- Reload containers and restart flows\n9 / CTRL+C -- Abort', TerminalColors.ENDC)

            value = sys.stdin.readline().strip()

            self.__ps_to_read.clear() # clear, so we do not read old processes
            for ps in ps_to_kill_tmp:
                print(f"Trying to kill detached process '{ps['cmd']}'' of current flow")
                try:
                    process_helpers.kill_pg(ps['ps'], ps['cmd'])
                except ProcessLookupError as process_exc: # Process might have done expected exit already. However all other errors shall bubble
                    print(f"Could not kill {ps['cmd']}. Exception: {process_exc}")

            if not exception_occured and value == '0':
                continue

            if value == '2':
                for _ in range(0,flow_id+1):
                    self.__phases.popitem(last=True)
                flow_id = 0
            elif value == '3':
                self.cleanup(continue_measurement=True)
                self.setup_networks()
                self.setup_services()
                flow_id = 0
            elif value == '9':
                raise KeyboardInterrupt("Manual abort")
            else: # implicit 1
                self.__phases.popitem(last=True)

    # this method should never be called twice to avoid double logging of metrics
    def stop_metric_providers(self):
        if self._dev_no_metrics:
            return

        print(TerminalColors.HEADER, 'Stopping metric providers and parsing measurements', TerminalColors.ENDC)
        errors = []
        for metric_provider in self.__metric_providers:
            if not metric_provider.has_started():
                continue

            stderr_read = metric_provider.get_stderr()
            if stderr_read:
                errors.append(f"Stderr on {metric_provider.__class__.__name__} was NOT empty: {stderr_read}")

            # pylint: disable=broad-exception-caught
            try:
                metric_provider.stop_profiling()
            except Exception as exc:
                errors.append(f"Could not stop profiling on {metric_provider.__class__.__name__}: {str(exc)}")

            df = metric_provider.read_metrics(self._run_id, self.__containers)
            if isinstance(df, int):
                print('Imported', TerminalColors.HEADER, df, TerminalColors.ENDC, 'metrics from ', metric_provider.__class__.__name__)
                # If df returns an int the data has already been committed to the db
                continue

            print('Imported', TerminalColors.HEADER, df.shape[0], TerminalColors.ENDC, 'metrics from ', metric_provider.__class__.__name__)
            if df is None or df.shape[0] == 0:
                errors.append(f"No metrics were able to be imported from: {metric_provider.__class__.__name__}")

            f = StringIO(df.to_csv(index=False, header=False))
            DB().copy_from(file=f, table='measurements', columns=df.columns, sep=',')
        self.__metric_providers.clear()
        if errors:
            raise RuntimeError("\n".join(errors))


    def read_and_cleanup_processes(self):
        print(TerminalColors.HEADER, '\nReading process stdout/stderr (if selected) and cleaning them up', TerminalColors.ENDC)

        for ps in self.__ps_to_kill:
            try:
                # we never need to kill a process group here, even if started in shell mode, as we funnel through docker exec
                process_helpers.kill_pg(ps['ps'], ps['cmd'])
            except ProcessLookupError as exc: # Process might have done expected exit already.
                print(f"Could not kill {ps['cmd']}. Exception: {exc}")
        self.__ps_to_kill.clear() # we need to clear, so we do not kill twice later

        for ps in self.__ps_to_read:
            if ps['detach']:
                # communicate will only really work to our experience if the process is killed before
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
                for line in stderr.splitlines():
                    print('stderr from process:', ps['cmd'], line)
                    self.add_to_log(ps['container_name'], f"stderr: {line}", ps['cmd'])

    def check_process_returncodes(self):
        print(TerminalColors.HEADER, '\nChecking process return codes', TerminalColors.ENDC)
        for ps in self.__ps_to_read:
            if not ps['ignore-errors']:
                # This block will read from a detached process via communicate
                # If the process is detached the returncode is only set after communicate has been called, even if it failed
                # If the process is still running the returncode will be None and it still runs
                try:
                    if ps['detach']:
                        _, stderr = ps['ps'].communicate(timeout=1)
                    else:
                        stderr = ps['ps'].stderr
                except subprocess.TimeoutExpired:
                    pass

                if process_helpers.check_process_failed(ps['ps'], ps['detach']):
                    raise RuntimeError(f"Process '{ps['cmd']}' had bad returncode: {ps['ps'].returncode}. Stderr: {stderr}; Detached process: {ps['detach']}. Please also check the stdout in the logs and / or enable stdout logging to debug further.")

    def start_measurement(self):
        self.__start_measurement = int(time.time_ns() / 1_000)
        self.__start_measurement_seconds = time.time()

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
            """, params=(self.__start_measurement, self.__end_measurement, self._run_id))

    def set_run_failed(self):
        if not self._run_id:
            return # Nothing to do, but also no hard error needed

        DB().query("""
            UPDATE runs
            SET failed = TRUE
            WHERE id = %s
            """, params=(self._run_id, ))


    def store_phases(self):
        print(TerminalColors.HEADER, '\nUpdating phases in DB', TerminalColors.ENDC)
        # internally PostgreSQL stores JSON ordered. This means our name-indexed dict will get
        # re-ordered. Therefore we change the structure and make it a list now.
        # We did not make this before, as we needed the duplicate checking of dicts
        phases = list(self.__phases.values())
        DB().query("""
            UPDATE runs
            SET phases=%s
            WHERE id = %s
            """, params=(json.dumps(phases), self._run_id))

    def read_container_logs(self):
        print(TerminalColors.HEADER, '\nCapturing container logs', TerminalColors.ENDC)
        for container_id, container_info in self.__containers.items():

            stderr_behaviour = stdout_behaviour = subprocess.DEVNULL
            if container_info['log-stdout'] is True:
                stdout_behaviour = subprocess.PIPE
            if container_info['log-stderr'] is True:
                stderr_behaviour = subprocess.PIPE

            log = subprocess.run(
                ['docker', 'logs', container_id],
                check=True,
                encoding='UTF-8',
                stdout=stdout_behaviour,
                stderr=stderr_behaviour,
            )

            if log.stdout:
                self.add_to_log(container_id, f"stdout: {log.stdout}")

                if container_info['read-notes-stdout'] or container_info['read-sci-stdout']:
                    for line in log.stdout.splitlines():
                        if container_info['read-notes-stdout']:
                            if note := self.__notes_helper.parse_note(line):
                                self.__notes_helper.add_note({'note': note[1], 'detail_name': container_info['name'], 'timestamp': note[0]})

                        if container_info['read-sci-stdout']:
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
                """, params=(logs_as_str, self._run_id))


    def cleanup(self, continue_measurement=False):
        #https://github.com/green-coding-berlin/green-metrics-tool/issues/97
        print(TerminalColors.OKCYAN, '\nStarting cleanup routine', TerminalColors.ENDC)

        if continue_measurement is False:
            print('Stopping metric providers')
            for metric_provider in self.__metric_providers:
                try:
                    metric_provider.stop_profiling()
                # pylint: disable=broad-exception-caught
                except Exception as exc:
                    error_helpers.log_error(f"Could not stop profiling on {metric_provider.__class__.__name__}", exception=exc)
            self.__metric_providers.clear()


        print('Stopping containers')
        for container_id in self.__containers:
            subprocess.run(['docker', 'rm', '-f', container_id], check=True, stderr=subprocess.DEVNULL)
        self.__containers = {}

        print('Removing network')
        for network_name in self.__networks:
            # no check=True, as the network might already be gone. We do not want to fail here
            subprocess.run(['docker', 'network', 'rm', network_name], stderr=subprocess.DEVNULL, check=False)
        self.__networks.clear()

        if continue_measurement is False:
            self.remove_docker_images()

        for ps in self.__ps_to_kill:
            try:
                process_helpers.kill_pg(ps['ps'], ps['cmd'])
            except ProcessLookupError as exc: # Process might have done expected exit already. However all other errors shall bubble
                print(f"Could not kill {ps['cmd']}. Exception: {exc}")


        print(TerminalColors.OKBLUE, '-Cleanup gracefully completed', TerminalColors.ENDC)

        self.__ps_to_kill.clear()
        self.__ps_to_read.clear()

        if continue_measurement is False:
            self.__start_measurement = None
            self.__start_measurement_seconds = None
            self.__notes_helper = Notes()

        self.__phases = OrderedDict()
        self.__end_measurement = None
        self.__join_default_network = False
        #self.__filename = self._original_filename # # we currently do not use this variable
        self.__working_folder = self._repo_folder
        self.__working_folder_rel = ''

        print(TerminalColors.OKBLUE, '-Cleanup gracefully completed', TerminalColors.ENDC)

    def run(self):
        '''
            The run method is just a wrapper for the intended sequential flow of a GMT run.
            Mainly designed to call the methods individually for testing, but also
            if the flow ever needs to repeat certain blocks.

            The runner is to be thought of as a state machine.

            Methods thus will behave differently given the runner was instantiated with different arguments.

        '''
        try:
            config = GlobalConfig().config
            self.check_system('start')
            self.initialize_folder(self._tmp_folder)
            self.checkout_repository()
            self.initialize_run()
            self.initial_parse()
            self.import_metric_providers()
            self.populate_image_names()
            self.prepare_docker()
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

            self.custom_sleep(config['measurement']['pre-test-sleep'])

            self.start_measurement()

            self.start_phase('[BASELINE]')
            self.custom_sleep(config['measurement']['baseline-duration'])
            self.end_phase('[BASELINE]')

            if self._debugger.active:
                self._debugger.pause('Measurements started. Waiting to start container build')

            self.start_phase('[INSTALLATION]')
            self.build_docker_images()
            self.end_phase('[INSTALLATION]')

            if self._debugger.active:
                self._debugger.pause('Container build complete. Waiting to start container boot')

            self.start_phase('[BOOT]')
            self.setup_networks()
            self.setup_services()
            self.end_phase('[BOOT]')

            if self._debugger.active:
                self._debugger.pause('Container setup complete. Waiting to start container providers')

            self.start_metric_providers(allow_container=True, allow_other=False)

            if self._debugger.active:
                self._debugger.pause('metric-providers (container) start complete. Waiting to start idle phase')

            self.start_phase('[IDLE]')
            self.custom_sleep(config['measurement']['idle-duration'])
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
            self.custom_sleep(config['measurement']['post-test-sleep'])
            self.store_phases()
            self.update_start_and_end_times()

        except BaseException as exc:
            self.add_to_log(exc.__class__.__name__, str(exc))
            self.set_run_failed()
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

        return self._run_id

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--uri', type=str, help='The URI to get the usage_scenario.yml from. Can be either a local directory starting  with / or a remote git repository starting with http(s)://')
    parser.add_argument('--branch', type=str, help='Optionally specify the git branch when targeting a git repository')
    parser.add_argument('--name', type=str, help='A name which will be stored to the database to discern this run from others')
    parser.add_argument('--filename', type=str, default='usage_scenario.yml', help='An optional alternative filename if you do not want to use "usage_scenario.yml"')
    parser.add_argument('--config-override', type=str, help='Override the configuration file with the passed in yml file. Must be located in the same directory as the regular configuration file. Pass in only the name.')
    parser.add_argument('--file-cleanup', action='store_true', help='Delete all temporary files that the runner produced')
    parser.add_argument('--debug', action='store_true', help='Activate steppable debug mode')
    parser.add_argument('--allow-unsafe', action='store_true', help='Activate unsafe volume bindings, ports and complex environment vars')
    parser.add_argument('--skip-unsafe', action='store_true', help='Skip unsafe volume bindings, ports and complex environment vars')
    parser.add_argument('--skip-system-checks', action='store_true', help='Skip checking the system if the GMT can run')
    parser.add_argument('--verbose-provider-boot', action='store_true', help='Boot metric providers gradually')
    parser.add_argument('--full-docker-prune', action='store_true', help='Stop and remove all containers, build caches, volumes and images on the system')
    parser.add_argument('--docker-prune', action='store_true', help='Prune all unassociated build caches, networks volumes and stopped containers on the system')
    parser.add_argument('--dev-flow-timetravel', action='store_true', help='Allows to repeat a failed flow or timetravel to beginning of flows or restart services.')
    parser.add_argument('--dev-no-metrics', action='store_true', help='Skips loading the metric providers. Runs will be faster, but you will have no metric')
    parser.add_argument('--dev-no-sleeps', action='store_true', help='Removes all sleeps. Resulting measurement data will be skewed.')
    parser.add_argument('--dev-no-build', action='store_true', help='Checks if a container image is already in the local cache and will then not build it. Also doesn\'t clear the images after a run. Please note that skipping builds only works the second time you make a run since the image has to be built at least initially to work.')
    parser.add_argument('--dev-no-optimizations', action='store_true', help='Disable analysis after run to find possible optimizations.')
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

    if args.dev_no_build and (args.docker_prune or args.full_docker_prune):
        parser.print_help()
        error_helpers.log_error('--dev-no-build blocks pruning docker images. Combination is not allowed')
        sys.exit(1)

    if args.full_docker_prune and GlobalConfig().config['postgresql']['host'] == 'green-coding-postgres-container':
        parser.print_help()
        error_helpers.log_error('--full-docker-prune is set while your database host is "green-coding-postgres-container".\nThe switch is only for remote measuring machines. It would stop the GMT images itself when running locally')
        sys.exit(1)

    if args.uri[0:8] == 'https://' or args.uri[0:7] == 'http://':
        print('Detected supplied URL: ', args.uri)
        run_type = 'URL'
    elif args.uri[0:1] == '/':
        print('Detected supplied folder: ', args.uri)
        run_type = 'folder'
        if not Path(args.uri).is_dir():
            parser.print_help()
            error_helpers.log_error('Could not find folder on local system. Please double check: ', uri=args.uri)
            sys.exit(1)
    else:
        parser.print_help()
        error_helpers.log_error('Could not detected correct URI. Please use local folder in Linux format /folder/subfolder/... or URL http(s):// : ', uri=args.uri)
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

    runner = Runner(name=args.name, uri=args.uri, uri_type=run_type, filename=args.filename,
                    branch=args.branch, debug_mode=args.debug, allow_unsafe=args.allow_unsafe,
                    skip_system_checks=args.skip_system_checks,
                    skip_unsafe=args.skip_unsafe,verbose_provider_boot=args.verbose_provider_boot,
                    full_docker_prune=args.full_docker_prune, dev_no_sleeps=args.dev_no_sleeps,
                    dev_no_build=args.dev_no_build, dev_no_metrics=args.dev_no_metrics,
                    dev_flow_timetravel=args.dev_flow_timetravel, dev_no_optimizations=args.dev_no_optimizations,
                    docker_prune=args.docker_prune)

    # Using a very broad exception makes sense in this case as we have excepted all the specific ones before
    #pylint: disable=broad-except
    try:
        run_id = runner.run()  # Start main code

        # this code should live at a different position.
        # From a user perspective it makes perfect sense to run both jobs directly after each other
        # In a cloud setup it however makes sense to free the measurement machine as soon as possible
        # So this code should be individually callable, separate from the runner

        print(TerminalColors.HEADER, '\nCalculating and storing phases data. This can take a couple of seconds ...', TerminalColors.ENDC)

        # get all the metrics from the measurements table grouped by metric
        # loop over them issuing separate queries to the DB
        from tools.phase_stats import build_and_store_phase_stats

        build_and_store_phase_stats(runner._run_id, runner._sci)

        # We need to import this here as we need the correct config file
        if not runner._dev_no_optimizations:
            import optimization_providers.base
            print(TerminalColors.HEADER, '\nImporting optimization reporters ...', TerminalColors.ENDC)
            optimization_providers.base.import_reporters()

            print(TerminalColors.HEADER, '\nRunning optimization reporters ...', TerminalColors.ENDC)

            optimization_providers.base.run_reporters(runner._run_id, runner._tmp_folder, runner.get_optimizations_ignore())

        if args.file_cleanup:
            shutil.rmtree(runner._tmp_folder)

        print(TerminalColors.OKGREEN,'\n\n####################################################################################')
        print(f"Please access your report on the URL {GlobalConfig().config['cluster']['metrics_url']}/stats.html?id={runner._run_id}")
        print('####################################################################################\n\n', TerminalColors.ENDC)

    except FileNotFoundError as e:
        error_helpers.log_error('File or executable not found', exception=e, run_id=runner._run_id)
    except subprocess.CalledProcessError as e:
        error_helpers.log_error('Command failed', stdout=e.stdout, stderr=e.stderr, run_id=runner._run_id)
    except RuntimeError as e:
        error_helpers.log_error('RuntimeError occured in runner.py', exception=e, run_id=runner._run_id)
    except BaseException as e:
        error_helpers.log_error('Base exception occured in runner.py', exception=e, run_id=runner._run_id)
    finally:
        if args.print_logs:
            for container_id_outer, std_out in runner.get_logs().items():
                print(f"Container logs of '{container_id_outer}':")
                print(std_out)
                print('\n-----------------------------\n')
