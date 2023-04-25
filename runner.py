#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# We disable naming convention to allow names like p,kv etc. Even if it is not 'allowed' it makes the code more readable
#pylint: disable=invalid-name

# As pretty much everything is done in one big flow we trigger all the too-many-* checks. Which normally makes sense
# but in this case it would make the code a lot more complicated separating this out into loads of sub-functions
#pylint: disable=too-many-branches,too-many-statements,too-many-arguments,too-many-instance-attributes

# Using a very broad exception makes sense in this case as we have excepted all the specific ones before
#pylint: disable=broad-except

# I can't make these go away, but the imports all work fine on my system >.<
#pylint: disable=wrong-import-position, import-error

import subprocess
import json
import os
import time
import sys
import importlib
import faulthandler
import re
from io import StringIO
import yaml

faulthandler.enable()  # will catch segfaults and write to STDERR

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{CURRENT_DIR}/lib")

from debug_helper import DebugHelper
from terminal_colors import TerminalColors
import schema_checker
import process_helpers
import hardware_info
import hardware_info_root
import error_helpers
from db import DB
from global_config import GlobalConfig
import utils
from tools.save_notes import save_notes  # local file import


def arrows(text):
    return f"\n\n>>>> {text} <<<<\n\n"

class Runner:
    def __init__(self,
        uri, uri_type, pid, filename='usage_scenario.yml', branch=None,
        debug_mode=False, allow_unsafe=False, no_file_cleanup=False, skip_unsafe=False,
        verbose_provider_boot=False):

        if skip_unsafe is True and allow_unsafe is True:
            raise RuntimeError('Cannot specify both --skip-unsafe and --allow-unsafe')

        self._debugger = DebugHelper(debug_mode)
        self._allow_unsafe = allow_unsafe
        self._no_file_cleanup = no_file_cleanup
        self._skip_unsafe = skip_unsafe
        self._verbose_provider_boot = verbose_provider_boot

        # variables that should not change if you call run multiple times
        self._uri = uri
        self._uri_type = uri_type
        self._project_id = pid
        self._filename = filename
        self._branch = branch
        self._folder = '/tmp/green-metrics-tool/repo' # default if not changed in checkout_repository
        self._usage_scenario = {}
        self._architecture = utils.get_architecture()


        # transient variables that are created by the runner itself
        # these are accessed and processed on cleanup and then reset
        self.__containers = {}
        self.__networks = []
        self.__ps_to_kill = []
        self.__ps_to_read = []
        self.__metric_providers = []
        self.__notes = [] # notes may have duplicate timestamps, therefore list and no dict structure
        self.__start_measurement = None
        self.__end_measurement = None

    def prepare_filesystem_location(self):
        subprocess.run(['rm', '-Rf', '/tmp/green-metrics-tool'], check=True, stderr=subprocess.DEVNULL)
        subprocess.run(['mkdir', '/tmp/green-metrics-tool'], check=True)


    def checkout_repository(self):

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
                        self._folder
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
                        self._folder
                    ],
                    check=True,
                    capture_output=True,
                    encoding='UTF-8'
                )  # always name target-dir repo according to spec

            commit_hash = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                check=True,
                capture_output=True,
                encoding='UTF-8',
                cwd=self._folder
            )
            commit_hash = commit_hash.stdout.strip("\n")

            DB().query("""UPDATE projects
                SET commit_hash=%s
                WHERE id = %s
                """,
                params=(commit_hash, self._project_id))


        else:
            if self._branch:
                raise RuntimeError('Specified --branch but using local URI. Did you mean to specify a github url?')
            self._folder = self._uri

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

                filename = os.path.realpath(os.path.join(self._root, nodes[0]))

                if not filename.startswith(self._root):
                    raise ImportError(f"Import tries to escape root! ({filename})")

                # To double check we also check if it is in the files allow list
                if filename not in [os.path.join(self._root, item) for item in os.listdir(self._root)]:
                    print(os.listdir(self._root))
                    raise RuntimeError(f"{filename} not in allowed file list")


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

        with open(f"{self._folder}/{self._filename}", 'r', encoding='utf-8') as fp:
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
            self._usage_scenario = yml_obj

    def initial_parse(self):

        self.load_yml_file()
        schema_checker.check_usage_scenario(self._usage_scenario)

        print(TerminalColors.HEADER, '\nHaving Usage Scenario ', self._usage_scenario['name'], TerminalColors.ENDC)
        print('From: ', self._usage_scenario['author'])
        print('Version ', self._usage_scenario['version'], '\n')

        if self._allow_unsafe:
            print(TerminalColors.WARNING, arrows('Warning: Runner is running in unsafe mode'), TerminalColors.ENDC)

        if self._usage_scenario.get('architecture') is not None and \
            self._architecture != self._usage_scenario['architecture'].lower():
            raise RuntimeError('Specified architecture does not match system architecture:'
                f"system ({self._architecture}) != specified ({self._usage_scenario.get('architecture')})")

    def update_and_insert_specs(self):
        config = GlobalConfig().config

        # There are two ways we get hardware info. First things we don't need to be root to do which we get through
        # a method call. And then things we need root privilege which we need to call as a subprocess with sudo. The
        # install.sh script should have called the makefile which adds the script to the sudoes file.
        machine_specs = hardware_info.get_default_values()

        if len(hardware_info_root.get_root_list()) > 0:
            python_file = os.path.abspath(os.path.join(CURRENT_DIR, 'lib/hardware_info_root.py'))
            ps = subprocess.run(['sudo', sys.executable, python_file],
                                stdout=subprocess.PIPE, check=True, encoding='UTF-8')
            machine_specs_root = json.loads(ps.stdout)

            machine_specs.update(machine_specs_root)

        # Insert auxilary info for the run. Not critical.
        DB().query("""UPDATE projects
            SET machine_specs=%s, measurement_config=%s, usage_scenario = %s, last_run = NOW()
            WHERE id = %s
            """, params=(
            json.dumps(machine_specs),
            json.dumps(config['measurement']),
            json.dumps(self._usage_scenario),
            self._project_id)
        )

    def import_metric_providers(self):
        config = GlobalConfig().config

        print(TerminalColors.HEADER, '\nImporting metric providers', TerminalColors.ENDC)

        metric_providers = utils.get_metric_providers(config)

        if not metric_providers:
            print(TerminalColors.WARNING,
                  arrows('No metric providers were configured in config.yml. Was this intentional?'),
                  TerminalColors.ENDC)
            return

        # will iterate over keys
        for metric_provider in metric_providers:
            module_path, class_name = metric_provider.rsplit('.', 1)
            module_path = f"metric_providers.{module_path}"

            print(f"Importing {class_name} from {module_path}")
            print(f"Configuration is {metric_providers[metric_provider]}")
            module = importlib.import_module(module_path)
            # the additional () creates the instance
            metric_provider_obj = getattr(module, class_name)(
                resolution=metric_providers[metric_provider]['resolution'])

            self.__metric_providers.append(metric_provider_obj)

        self.__metric_providers.sort(key=lambda item: 'rapl' not in item.__class__.__name__.lower())

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

    def setup_services(self):
        for container_name in self._usage_scenario['services']:
            print(TerminalColors.HEADER, '\nSetting up containers', TerminalColors.ENDC)

            service = self._usage_scenario['services'][container_name]

            print('Resetting container')
            # often not running. so no check=true
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
                docker_run_string.append(f"{self._folder}:{service['folder-destination']}:ro")
            else:
                docker_run_string.append(f"{self._folder}:/tmp/repo:ro")

            if 'volumes' in service:
                if self._allow_unsafe:
                    # On old docker clients we experience some weird error, that we deem legacy
                    # If a volum is supplied in the compose.yml file in this form: ./file.txt:/tmp/file.txt
                    # and the file does NOT exist, then docker will create the folder in the current running dir
                    # This is however not enabled anymore and hard to circumvent. We keep this as unfixed for now.
                    if not isinstance(service['volumes'], list):
                        raise RuntimeError(f"Volumes must be a list but is: {type(service['volumes'])}")
                    for volume in service['volumes']:
                        docker_run_string.append('-v')
                        docker_run_string.append(f"{volume}")
                else: # safe volume bindings are active by default
                    if not isinstance(service['volumes'], list):
                        raise RuntimeError(f"Volumes must be a list but is: {type(service['volumes'])}")
                    for volume in service['volumes']:
                        vol = volume.split(':')
                        # We always assume the format to be ./dir:dir:[flag] as if we allow none bind mounts people
                        # could create volumes that would linger on our system.
                        path = os.path.realpath(os.path.join(self._folder, vol[0]))
                        if not os.path.exists(path):
                            raise RuntimeError(f"Volume path does not exist {path}")

                        # Check that the path starts with self._folder
                        if not path.startswith(self._folder):
                            raise RuntimeError(f"Trying to escape folder {path}")

                        # To double check we also check if it is in the files allow list
                        if path not in [os.path.join(self._folder, item) for item in os.listdir(self._folder)]:
                            print( os.listdir(self._folder))
                            raise RuntimeError(f"{path} not in allowed file list")

                        if len(vol) == 3:
                            if vol[2] != 'ro':
                                raise RuntimeError('We only allow ro as parameter in volume mounts in unsafe mode')

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
                    print(TerminalColors.WARNING,
                          arrows('Found ports entry but not running in unsafe mode. Skipping'),
                          TerminalColors.ENDC)
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
                        raise RuntimeError(f"Environment variable needs to be a string with = or dict!")

                    True, True
                    if not self._allow_unsafe and re.search(r'^[A-Z_]+$', env_key) is None:
                        if self._skip_unsafe:
                            warn_message= arrows(f"Found environment var key with wrong format. \
                                 Only ^[A-Z_]+$ allowed: {env_key} - Skipping")
                            print(TerminalColors.WARNING, warn_message, TerminalColors.ENDC)
                            continue
                        raise RuntimeError(f"Docker container setup environment var key had wrong format. \
                            Only ^[A-Z_]+$ allowed: {env_key} - Maybe consider using --allow-unsafe \
                                or --skip-unsafe")

                    if not self._allow_unsafe and \
                        re.search(r'^[a-zA-Z0-9_]+[a-zA-Z0-9_-]*$', env_value) is None:
                        if self._skip_unsafe:
                            print(TerminalColors.WARNING, arrows(f"Found environment var value with wrong format. \
                                    Only ^[A-Z_]+[a-zA-Z0-9_]*$ allowed: {env_value} - \
                                    Skipping"), TerminalColors.ENDC)
                            continue
                        raise RuntimeError(f"Docker container setup environment var value had wrong format. \
                            Only ^[A-Z_]+[a-zA-Z0-9_]*$ allowed: {env_value} - \
                            Maybe consider using --allow-unsafe --skip-unsafe")

                    docker_run_string.append('-e')
                    docker_run_string.append(f"{env_key}={env_value}")

            if 'networks' in service:
                for network in service['networks']:
                    docker_run_string.append('--net')
                    docker_run_string.append(network)

            docker_run_string.append(service['image'])

            if 'cmd' in service:  # must come last
                docker_run_string.append(service['cmd'])

            print(f"Running docker run with: {' '.join(docker_run_string)}")

            # docker_run_string must stay as list, cause this forces items to be quoted and escaped and prevents
            # injection of unwawnted params

            ps = subprocess.run(
                docker_run_string,
                check=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                encoding='UTF-8'
            )

            container_id = ps.stdout.strip()
            self.__containers[container_id] = container_name
            print('Stdout:', container_id)

            if 'setup-commands' not in service:
                continue  # setup commands are optional
            print('Running commands')
            for cmd in service['setup-commands']:
                d_command = ['docker', 'exec', container_name, 'sh', '-c', cmd] # This must be a list!
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


    def start_metric_providers(self):
        print(TerminalColors.HEADER, '\nStarting metric providers', TerminalColors.ENDC)

        for metric_provider in self.__metric_providers:
            message = f"Booting {metric_provider.__class__.__name__}"
            print(message)
            metric_provider.start_profiling(self.__containers)
            if self._verbose_provider_boot:
                self.__notes.append({'note': message, 'detail_name': '[SYSTEM]', 'timestamp': int(
                    time.time_ns() / 1_000)})
                time.sleep(10)

        print(TerminalColors.HEADER, '\nWaiting for Metric Providers to boot ...', TerminalColors.ENDC)
        time.sleep(2)

        for metric_provider in self.__metric_providers:
            stderr_read = metric_provider.get_stderr()
            print(f"Stderr check on {metric_provider.__class__.__name__}")
            if stderr_read is not None:
                raise RuntimeError(f"Stderr on {metric_provider.__class__.__name__} was NOT empty: {stderr_read}")

    def pre_idle_containers(self):
        config = GlobalConfig().config
        print(TerminalColors.HEADER,
              f"\nPre-idling containers for {config['measurement']['idle-time-start']}s", TerminalColors.ENDC)
        self.__notes.append({'note': 'Pre-idling containers',
                     'detail_name': '[SYSTEM]', 'timestamp': int(time.time_ns() / 1_000)})

        time.sleep(config['measurement']['idle-time-start'])


    def start_measurement(self):
        self.__start_measurement = int(time.time_ns() / 1_000)
        self.__notes.append({'note': 'Start of measurement',
                     'detail_name': '[SYSTEM]', 'timestamp': self.__start_measurement})


    def run_flows(self):
        config = GlobalConfig().config
        try:
            # run the flows
            for el in self._usage_scenario['flow']:
                print(TerminalColors.HEADER, '\nRunning flow: ', el['name'], TerminalColors.ENDC)
                for inner_el in el['commands']:
                    if 'note' in inner_el:
                        self.__notes.append({'note': inner_el['note'], 'detail_name': el['container'],
                            'timestamp': int(time.time_ns() / 1_000)})

                    if inner_el['type'] == 'console':
                        print(TerminalColors.HEADER, '\nConsole command',
                              inner_el['command'], 'on container', el['container'], TerminalColors.ENDC)

                        docker_exec_command = ['docker', 'exec']

                        docker_exec_command.append(el['container'])
                        docker_exec_command.append('sh')
                        docker_exec_command.append('-c')
                        docker_exec_command.append(inner_el['command'])

                        # Note: In case of a detach wish in the usage_scenario.yml:
                        # We are NOT using the -d flag from docker exec, as this prohibits getting the stdout.
                        # Since Popen always make the process asynchronous we can leverage this to emulate a detached
                        # behavior

                        #pylint: disable=consider-using-with
                        ps = subprocess.Popen(
                            docker_exec_command,
                            stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            encoding='UTF-8'
                            )

                        self.__ps_to_read.append({
                            'cmd': docker_exec_command,
                            'ps': ps,
                            'read-notes-stdout': inner_el.get('read-notes-stdout', False),
                            'ignore-errors': inner_el.get('ignore-errors', False),
                            'detail_name': el['container'],
                            'detach': inner_el.get('detach', False),
                        })

                        if inner_el.get('detach', False) is True:
                            print('Process should be detached. Running asynchronously and detaching ...')
                            self.__ps_to_kill.append({'ps': ps, 'cmd': inner_el['command'], 'ps_group': False})
                        else:
                            print(f"Process should be synchronous. \
                                Alloting {config['measurement']['flow-process-runtime']}s runtime ...")
                            process_helpers.timeout(
                                ps, inner_el['command'], config['measurement']['flow-process-runtime'])
                    else:
                        raise RuntimeError('Unknown command type in flow: ', inner_el['type'])

                    if self._debugger.active:
                        self._debugger.pause('Waiting to start next command in flow')

            self.__end_measurement = int(time.time_ns() / 1_000)
            self.__notes.append({'note': 'End of measurement', 'detail_name': '[SYSTEM]',
                                'timestamp': self.__end_measurement})

            print(TerminalColors.HEADER,
                  f"\nIdling containers after run for {config['measurement']['idle-time-end']}s", TerminalColors.ENDC)

            time.sleep(config['measurement']['idle-time-end'])

            self.__notes.append({'note': 'End of post-measurement idle',
                'detail_name': '[SYSTEM]', 'timestamp': int(time.time_ns() / 1_000)})

            print(TerminalColors.HEADER, 'Stopping metric providers and parsing stats', TerminalColors.ENDC)
            for metric_provider in self.__metric_providers:
                stderr_read = metric_provider.get_stderr()
                if stderr_read is not None:
                    raise RuntimeError(
                        f"Stderr on {metric_provider.__class__.__name__} was NOT empty: {stderr_read}")

                metric_provider.stop_profiling()

                df = metric_provider.read_metrics(self._project_id, self.__containers)
                print('Imported', TerminalColors.HEADER,
                      df.shape[0], TerminalColors.ENDC, 'metrics from ', metric_provider.__class__.__name__)
                if df is None or df.shape[0] == 0:
                    raise RuntimeError(
                        f"No metrics were able to be imported from: {metric_provider.__class__.__name__}")

                f = StringIO(df.to_csv(index=False, header=False))
                DB().copy_from(file=f, table='stats', columns=df.columns, sep=',')

            # kill process only after reading. Otherwise the stream buffer might be gone
            process_helpers.kill_ps(self.__ps_to_kill)

            # now we have free capacity to parse the stdout / stderr of the processes
            print(TerminalColors.HEADER, '\nGetting output from processes: ', TerminalColors.ENDC)
            for ps in self.__ps_to_read:
                for line in process_helpers.parse_stream_generator(ps['ps'], ps['cmd'], ps['ignore-errors'], ps['detach']):
                    print('Output from process: ', line)
                    if ps['read-notes-stdout']:
                        # Fixed format according to our specification. If unpacking fails this is wanted error
                        timestamp, note = line.split(' ', 1)
                        self.__notes.append({'note': note, 'detail_name': ps['detail_name'], 'timestamp': timestamp})

        finally:
            # we here only want the header to be colored, not the notes itself
            print(TerminalColors.HEADER, '\nSaving notes: ', TerminalColors.ENDC, self.__notes)
            save_notes(self._project_id, self.__notes)

    def update_start_and_end_times(self):
        print(TerminalColors.HEADER, '\nUpdating start and end measurement times', TerminalColors.ENDC)
        DB().query("""UPDATE projects
            SET start_measurement=%s, end_measurement=%s
            WHERE id = %s
            """, params=(self.__start_measurement, self.__end_measurement, self._project_id))

    def cleanup(self):
        #https://github.com/green-coding-berlin/green-metrics-tool/issues/97
        print(TerminalColors.OKCYAN, '\nStarting cleanup routine', TerminalColors.ENDC)

        print('Stopping metric providers')
        for metric_provider in self.__metric_providers:
            metric_provider.stop_profiling()

        print('Stopping containers')
        for container_name in self.__containers.values():
            subprocess.run(['docker', 'rm', '-f', container_name], check=True, stderr=subprocess.DEVNULL)

        print('Removing network')
        for network_name in self.__networks:
            # no check=True, as the network might already be gone. We do not want to fail here
            subprocess.run(['docker', 'network', 'rm', network_name], stderr=subprocess.DEVNULL, check=False)

        if not self._no_file_cleanup:
            print('Removing files')
            subprocess.run(['rm', '-Rf', '/tmp/green-metrics-tool'], stderr=subprocess.DEVNULL, check=True)

        process_helpers.kill_ps(self.__ps_to_kill)
        print(TerminalColors.OKBLUE, '-Cleanup gracefully completed', TerminalColors.ENDC)

        self.__notes = []
        self.__containers = {}
        self.__networks = []
        self.__ps_to_kill = []
        self.__ps_to_read = []
        self.__metric_providers = []
        self.__start_measurement = None
        self.__end_measurement = None


    def run(self):
        '''
            The run function is just a wrapper for the intended sequential flow of a GMT run.
            Mainly designed to call the functions individually for testing, but also
            if the flow ever needs to repeat certain blocks.

            The runner is to be thought of as a state machine.

            Methods thus will behave differently given the runner was instantiated with different arguments.

        '''
        try:
            self.prepare_filesystem_location()
            self.checkout_repository()
            self.initial_parse()
            self.update_and_insert_specs()
            self.import_metric_providers()
            if self._debugger.active:
                self._debugger.pause('Initial load complete. Waiting to start network setup')
            self.setup_networks()

            if self._debugger.active:
                self._debugger.pause('Network setup complete. Waiting to start container setup')

            self.setup_services()

            if self._debugger.active:
                self._debugger.pause('Container setup complete. Waiting to start metric-providers')

            self.start_metric_providers()
            if self._debugger.active:
                self._debugger.pause('metric-providers start complete. Waiting to start flow')

            self.pre_idle_containers()
            self.start_measurement()
            self.run_flows() # can trigger debug breakpoints
            self.update_start_and_end_times()
        finally:
            self.cleanup()  # always run cleanup automatically after each run

        print(TerminalColors.OKGREEN, arrows('MEASUREMENT SUCCESSFULLY COMPLETED'), TerminalColors.ENDC)


if __name__ == '__main__':
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--uri', type=str, help='The URI to get the usage_scenario.yml from. Can be either a local directory starting \
            with / or a remote git repository starting with http(s)://')
    parser.add_argument(
        '--branch', type=str, help='Optionally specify the git branch when targeting a git repository')
    parser.add_argument(
        '--name', type=str, help='A name which will be stored to the database to discern this run from others')
    parser.add_argument(
        '--filename', type=str, default='usage_scenario.yml',
        help='An optional alternative filename if you do not want to use "usage_scenario.yml"')

    parser.add_argument(
        '--config-override', type=str, help='Override the configuration file with the passed in yml file. Must be \
        located in the same directory as the regular configuration file. Pass in only the name.')

    parser.add_argument('--no-file-cleanup', action='store_true',
                        help='Do not delete files in /tmp/green-metrics-tool')
    parser.add_argument('--debug', action='store_true',
                        help='Activate steppable debug mode')
    parser.add_argument('--allow-unsafe', action='store_true',
                        help='Activate unsafe volume bindings, ports and complex environment vars')
    parser.add_argument('--skip-unsafe', action='store_true',
                        help='Skip unsafe volume bindings, ports and complex environment vars')
    parser.add_argument('--verbose-provider-boot',
                        action='store_true', help='Boot metric providers gradually')

    args = parser.parse_args()

    if args.uri is None:
        parser.print_help()
        error_helpers.log_error('Please supply --uri to get usage_scenario.yml from')
        sys.exit(1)

    if args.allow_unsafe and args.skip_unsafe:
        parser.print_help()
        error_helpers.log_error('--allow-unsafe and skip--unsafe in conjuction is not possible')
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
        error_helpers.log_error('Could not detected correct URI. \
            Please use local folder in Linux format /folder/subfolder/... or URL http(s):// : ', args.uri)
        sys.exit(1)

    if args.config_override is not None:
        if args.config_override[-4:] != '.yml':
            parser.print_help()
            error_helpers.log_error('Config override file must be a yml file')
            sys.exit(1)
        if not Path(f"{CURRENT_DIR}/{args.config_override}").is_file():
            parser.print_help()
            error_helpers.log_error(f"Could not find config override file on local system.\
                Please double check: {CURRENT_DIR}/{args.config_override}")
            sys.exit(1)
        GlobalConfig(config_name=args.config_override)

    # We issue a fetch_one() instead of a query() here, cause we want to get the project_id
    project_id = DB().fetch_one('INSERT INTO "projects" ("name","uri","email","last_run","created_at", "branch") \
                VALUES \
                (%s,%s,\'manual\',NULL,NOW(),%s) RETURNING id;', params=(args.name, args.uri, args.branch))[0]

    runner = Runner(uri=args.uri, uri_type=run_type, pid=project_id, filename=args.filename,
                    branch=args.branch, debug_mode=args.debug, allow_unsafe=args.allow_unsafe,
                    no_file_cleanup=args.no_file_cleanup, skip_unsafe=args.skip_unsafe,
                    verbose_provider_boot=args.verbose_provider_boot)
    try:
        runner.run()  # Start main code
        print(TerminalColors.OKGREEN,
            '\n\n####################################################################################')
        print(f"Please access your report with the ID: {project_id}")
        print('####################################################################################\n\n',
            TerminalColors.ENDC)

    except FileNotFoundError as e:
        error_helpers.log_error('Docker command failed.', e, project_id)
    except subprocess.CalledProcessError as e:
        error_helpers.log_error(
            'Docker command failed', 'Stdout:', e.stdout, 'Stderr:', e.stderr, project_id)
    except KeyError as e:
        error_helpers.log_error(
            'Was expecting a value inside the usage_scenario.yml file, but value was missing: ', e, project_id)
    except RuntimeError as e:
        error_helpers.log_error(
            'RuntimeError occured in runner.py: ', e, project_id)
    except BaseException as e:
        error_helpers.log_error(
            'Base exception occured in runner.py: ', e, project_id)
