#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import shlex
import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from lib.venv_checker import check_venv
check_venv() # this check must even run before __main__ as imports might not get resolved

import subprocess
import json
import os
import time
import importlib
import re
from pathlib import Path
import random
import shutil
import yaml
from collections import OrderedDict
from datetime import datetime
import platform
from concurrent.futures import ThreadPoolExecutor
from energy_dependency_inspector import resolve_docker_dependencies_as_dict

GMT_ROOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../')

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
from lib.machine import Machine
from lib import metric_importer
from lib import container_compatibility
from lib.container_compatibility import CompatibilityStatus
from lib.log_types import LogType

def arrows(text):
    return f"\n\n>>>> {text} <<<<\n\n"

def validate_usage_scenario_variables(usage_scenario_variables):
    for key, _ in usage_scenario_variables.items():
        if not re.fullmatch(r'__GMT_VAR_[\w]+__', key):
            raise ValueError(f"Usage Scenario variable ({key}) has invalid name. Format must be __GMT_VAR_[\\w]+__ - Example: __GMT_VAR_EXAMPLE__")
    return usage_scenario_variables

class ScenarioRunner:
    def __init__(self,
        *, uri, uri_type, name=None, filename='usage_scenario.yml', branch=None,
        debug_mode=False, allow_unsafe=False,  skip_system_checks=False,
        skip_unsafe=False, verbose_provider_boot=False, full_docker_prune=False,
        dev_no_sleeps=False, dev_cache_build=False, dev_no_metrics=False,
        dev_flow_timetravel=False, dev_no_optimizations=False, docker_prune=False, job_id=None,
        user_id=1, measurement_flow_process_duration=None, measurement_total_duration=None, disabled_metric_providers=None, allowed_run_args=None, dev_no_phase_stats=False, dev_no_save=False,
        skip_volume_inspect=False, commit_hash_folder=None, usage_scenario_variables=None, phase_padding=True,
        measurement_system_check_threshold=3, measurement_pre_test_sleep=5, measurement_idle_duration=60,
        measurement_baseline_duration=60, measurement_post_test_sleep=5, measurement_phase_transition_time=1,
        measurement_wait_time_dependencies=60):

        self._arguments = locals() # safe the argument as first step before anything else to not expose local created variables

        config = GlobalConfig().config

        # sanity checks
        if skip_unsafe is True and allow_unsafe is True:
            raise ValueError('Cannot specify both --skip-unsafe and --allow-unsafe')

        if dev_cache_build and (docker_prune or full_docker_prune):
            raise ValueError('--dev-cache-build blocks pruning docker images. Combination is not allowed')

        if full_docker_prune and \
            config['postgresql']['host'] in ('green-coding-postgres-container', 'test-green-coding-postgres-container') :
            raise ValueError('--full-docker-prune is set while your database host is "(test)-green-coding-postgres-container".\nThe switch is only for remote measuring machines. It would stop the GMT images itself when running locally')

        # variables that should not change if you call run multiple times
        if name:
            self._name = name
        else:
            self._name = f"Run {datetime.now()}"
        self._debugger = DebugHelper(debug_mode)
        self._allow_unsafe = allow_unsafe
        self._skip_unsafe = skip_unsafe
        self._skip_system_checks = skip_system_checks
        self._skip_volume_inspect = skip_volume_inspect
        self._verbose_provider_boot = verbose_provider_boot
        self._full_docker_prune = full_docker_prune
        self._docker_prune = docker_prune
        self._dev_no_sleeps = dev_no_sleeps
        self._dev_cache_build = dev_cache_build
        self._dev_no_metrics = dev_no_metrics
        self._dev_flow_timetravel = dev_flow_timetravel
        self._dev_no_optimizations = dev_no_optimizations
        self._dev_no_phase_stats = dev_no_phase_stats
        self._dev_no_save = dev_no_save
        self._uri = uri
        self._uri_type = uri_type
        self._original_filename = filename
        self._branch = branch
        self._original_branch = branch  # Track original branch value to distinguish user-specified from auto-detected
        self._tmp_folder = Path('/tmp/green-metrics-tool').resolve() # since linux has /tmp and macos /private/tmp
        self._usage_scenario = {}
        self._usage_scenario_variables = validate_usage_scenario_variables(usage_scenario_variables) if usage_scenario_variables else {}
        self._architecture = utils.get_architecture()

        self._sci = {'R_d': None, 'R': 0}
        self._sci |= config.get('sci', None)  # merge in data from machine config like I, TE etc.

        self._job_id = job_id
        self._repo_folder = f"{self._tmp_folder}/repo" # default if not changed in checkout_repository
        self._run_id = None
        self._commit_hash = None
        self._commit_timestamp = None

        self._commit_hash_folder = commit_hash_folder if commit_hash_folder else ''
        self._user_id = user_id
        self._measurement_flow_process_duration = measurement_flow_process_duration
        self._measurement_total_duration = measurement_total_duration
        self._disabled_metric_providers = [] if disabled_metric_providers is None else disabled_metric_providers
        self._allowed_run_args = [] if allowed_run_args is None else allowed_run_args # They are specific to the orchestrator. However currently we only have one. As soon as we support more orchestrators we will sub-class Runner with dedicated child classes (DockerRunner, PodmanRunner etc.)
        self._measurement_system_check_threshold = measurement_system_check_threshold
        self._measurement_pre_test_sleep = measurement_pre_test_sleep
        self._measurement_idle_duration = measurement_idle_duration
        self._measurement_baseline_duration = measurement_baseline_duration
        self._measurement_post_test_sleep = measurement_post_test_sleep
        self._measurement_phase_transition_time = measurement_phase_transition_time
        self._measurement_wait_time_dependencies = measurement_wait_time_dependencies
        self._last_measurement_duration = 0
        self._phase_padding = phase_padding
        self._phase_padding_ms = max(
            utils.get_metric_providers(config, self._disabled_metric_providers).values(),
            key=lambda x: x.get('sampling_rate', 0) if x else 0
        ).get('sampling_rate', 0)

        del self._arguments['self'] # self is not needed and also cannot be serialzed. We remove it
        self._safe_post_processing_steps = (
                ('_end_measurement',  {'skip_on_already_ended': True}),
                ('_patch_phases', {}),
                ('_read_container_logs', {}),
                ('_stop_metric_providers', {}),
                ('_read_and_cleanup_processes', {}),
                ('_store_phases', {}),
                ('_save_notes_runner', {}),
                ('_save_run_logs', {}),
                ('_save_warnings', {}),
                ('_process_phase_stats', {}),
            )

        # transient variables that are created by the runner itself
        # these are accessed and processed on cleanup and then reset
        # They are __ as they should not be changed because this could break the state of the runner
        self.__current_run_logs = {}  # Dict with container names as keys, lists of log entries as values
        self.__all_runs_logs = []  # List of runs, each containing iteration, filename, and containers with their logs
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
        self.__image_sizes = {}
        self.__volume_sizes = {}
        self.__warnings = []
        self.__usage_scenario_dependencies = None
        self.__usage_scenario_variables_used_buffer = set(self._usage_scenario_variables.keys())
        self.__include_playwright_ipc_version = None

        self._check_all_durations()


    def _check_all_durations(self):
        if self._measurement_total_duration is None: # exit early if no max timeout specififed
            return

        durations = {
            'measurement_flow_process_duration': self._measurement_flow_process_duration,
            'pre_test_sleep': self._measurement_pre_test_sleep,
            'post_test_sleep': self._measurement_post_test_sleep,
            'idle_duration': self._measurement_idle_duration,
            'baseline_duration': self._measurement_baseline_duration,
            'phase_transition_time': self._measurement_phase_transition_time,
            'wait_time_dependencies': self._measurement_wait_time_dependencies,
        }

        for key, value in durations.items():
            if value is not None and value > self._measurement_total_duration:
                raise ValueError(f"Cannot run flows due to configuration error. Measurement_total_duration must be >= {key}, otherwise the flow will run into a timeout in every case. Values are: {key}: {value} and measurement_total_duration: {self._measurement_total_duration}")


    def _custom_sleep(self, sleep_time):
        if not self._dev_no_sleeps:
            print(TerminalColors.HEADER, '\nSleeping for : ', sleep_time, TerminalColors.ENDC)
            time.sleep(sleep_time)

    def get_optimizations_ignore(self):
        return self._usage_scenario.get('optimizations_ignore', [])

    # This function takes a path and a file and joins them while making sure that no one is trying to escape the
    # path with `..`, symbolic links or similar.
    # We always return the same error message including the path and file parameter, never `filename` as
    # otherwise we might disclose if certain files exist or not.
    def _join_paths(self, path, path2, force_path_as_root=False, force_path_in_repo=True):
        filename = os.path.realpath(os.path.join(path, path2))

        # If the original path is a symlink we need to resolve it.
        path = os.path.realpath(path)

        # This is a special case in which the file is '.'
        if filename == path.rstrip('/'):
            return filename

        if force_path_in_repo and not filename.startswith(self._repo_folder):
            raise ValueError(f"{path2} must not be in folder above root repo folder {self._repo_folder}")

        if force_path_as_root and not filename.startswith(path):
            raise RuntimeError(f"{path2} must not be in folder above {path}")

        # Another way to implement this. This is checking again but we want to be extra secure 👾
        if force_path_in_repo and Path(self._repo_folder).resolve(strict=True) not in Path(path, path2).resolve(strict=True).parents:
            raise ValueError(f"{path2} must not be in folder above root repo folder {self._repo_folder}")

        if force_path_as_root and Path(path).resolve(strict=True) not in Path(path, path2).resolve(strict=True).parents:
            raise ValueError(f"{path2} must not be in folder above {path}")


        if os.path.exists(filename):
            return filename

        raise FileNotFoundError(f"{path2} in {path} not found")


    def _initialize_folder(self, path):
        shutil.rmtree(path, ignore_errors=True)
        Path(path).mkdir(parents=True, exist_ok=True)

    def _save_notes_runner(self):
        print(TerminalColors.HEADER, '\nSaving notes: ', TerminalColors.ENDC, self.__notes_helper.get_notes())

        if not self._run_id or self._dev_no_save:
            print('Skipping saving notes due to missing run_id or --dev-no-save')
            return # Nothing to do, but also no hard error needed

        self.__notes_helper.save_to_db(self._run_id)

    def _clear_caches(self):
        subprocess.check_output(['sync'])

        if platform.system() == 'Darwin':
            return
        # 3 instructs kernel to drops page caches AND inode caches
        subprocess.check_output(['sudo', '/usr/sbin/sysctl', '-w', 'vm.drop_caches=3'])

    def _check_system(self, mode='start'):
        print(TerminalColors.HEADER, '\nChecking system', TerminalColors.ENDC)
        if self._skip_system_checks:
            print('Skipping check system due to --skip-system-checks')
            return

        warnings = system_checks.system_check(mode, self._measurement_system_check_threshold, run_duration=self._last_measurement_duration)
        for warn in warnings:
            self.__warnings.append(warn)


    def _checkout_repository(self):
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

            if problematic_symlink := utils.find_outside_symlinks(self._repo_folder):
                raise RuntimeError(f"Repository contained outside symlink: {problematic_symlink}\nGMT cannot handle this in URL or Cluster mode due to security concerns. Please change or remove the symlink or run GMT locally.")

            # Fix permissions to allow access from different users inside Docker containers
            # In some environments like GitHub Codespaces, directories may be created without
            # execute permission for 'other', preventing container users from traversing them
            subprocess.run(['chmod', '-R', 'o+X', self._repo_folder], check=True)
        else:
            if self._original_branch is not None:
                # we never want to checkout a local directory to a different branch as this might also be the GMT directory itself and might confuse the tool
                raise RuntimeError('Specified --branch but using local URI. Did you mean to specify a github url?')
            # If the provided uri is a symlink we need to resolve it.
            path = os.path.realpath(self._uri)
            self.__working_folder = self._repo_folder = path

        if self._dev_no_save:
            return

        self._branch = subprocess.check_output(['git', 'branch', '--show-current'], cwd=self._repo_folder, encoding='UTF-8', errors='replace').strip()

        git_repo_root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=self._repo_folder, encoding='UTF-8', errors='replace').strip()
        if git_repo_root != self._repo_folder:
            raise RuntimeError(f"Supplied folder through --uri is not the root of the git repository. Please only supply the root folder and then the target directory through --filename. Real repo root is {git_repo_root}")

        # we can safely do this, even with problematic folders, as the folder can only be a local unsafe one when
        # running in CLI mode
        self._commit_hash, self._commit_timestamp = get_repo_info(self._join_paths(self._repo_folder, self._commit_hash_folder))



    # This method loads the yml file and takes care that the includes work and are secure.
    # It uses the tagging infrastructure provided by https://pyyaml.org/wiki/PyYAMLDocumentation
    # Inspiration from https://github.com/tanbro/pyyaml-include which we can't use as it doesn't
    # do security checking and has no option to select when imported
    def _load_yml_file(self):
        #pylint: disable=too-many-ancestors
        runner_join_paths = self._join_paths
        usage_scenario_file = self._join_paths(self._repo_folder, self._original_filename)

        def uc_string_replace(uc_string, old, new):
            new_uc = uc_string.replace(old, new)
            if new_uc != uc_string:
                if old in self.__usage_scenario_variables_used_buffer:
                    self.__usage_scenario_variables_used_buffer.remove(old)

            return new_uc

        def replace_usage_scenario_variables(usage_scenario, usage_scenario_variables):
            for key, value in usage_scenario_variables.items():
                usage_scenario = uc_string_replace(usage_scenario, key, value)

            if matches := re.findall(r'^(?![\s]*#).*__GMT_VAR_\w+__', usage_scenario, re.MULTILINE):
                raise ValueError(f"Unreplaced leftover variables are still in usage_scenario: {matches} \n\n {usage_scenario}. \n\n Please add variables when submitting run.")

            return usage_scenario

        def make_loader(replacer, usage_scenario_variables, usage_scenario_file):
            class Loader(yaml.SafeLoader):
                def get_constructed_nodes(self, node):
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

                    return nodes

                def process_include(self, filename, nodes):
                    with open(filename, 'r', encoding='UTF-8') as f:
                        usage_scenario = f.read()

                    usage_scenario = replacer(usage_scenario, usage_scenario_variables)

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
                        return yaml.load(usage_scenario, Loader)

                    return recursive_lookup(nodes[1], yaml.load(usage_scenario, Loader))

            def include_gmt_helper(loader: Loader, node):
                nodes = loader.get_constructed_nodes(node)

                if not re.fullmatch(r'gmt-playwright-(?:with-cache-)?(v\d+.\d+.\d+)\.yml', nodes[0]):
                    raise ValueError(f"You tried include unallowed files with !include-gmt-helper function. Included files must conform to regex gmt-playwright-(?:with-cache-)?(v\\d+.\\d+.\\d+)\\.yml but actually is {nodes[0]}")

                filename = runner_join_paths(f"{GMT_ROOT_DIR}/templates/partials/", nodes[0], force_path_as_root=True, force_path_in_repo=False)

                return loader.process_include(filename, nodes)

            def include(loader: Loader, node):
                nodes = loader.get_constructed_nodes(node)

                try:
                    usage_scenario_dir = os.path.split(usage_scenario_file)[0]
                    filename = runner_join_paths(usage_scenario_dir, nodes[0], force_path_as_root=True)
                except RuntimeError as exc:
                    raise ValueError(f"Included compose file \"{nodes[0]}\" may only be in the same directory as the usage_scenario file as otherwise relative context_paths and volume_paths cannot be mapped anymore") from exc

                return loader.process_include(filename, nodes)

            Loader.add_constructor('!include', include)
            Loader.add_constructor('!include-gmt-helper', include_gmt_helper)
            return Loader


        # We set the working folder now to the actual location of the usage_scenario
        if '/' in self._original_filename:
            self.__working_folder_rel = self._original_filename.rsplit('/', 1)[0]
            self.__working_folder = usage_scenario_file.rsplit('/', 1)[0]
            print("Working folder changed to ", self.__working_folder)


        with open(usage_scenario_file, 'r', encoding='utf-8') as f:
            usage_scenario = f.read()
            usage_scenario = replace_usage_scenario_variables(usage_scenario, self._usage_scenario_variables)

            Loader = make_loader(
                replacer=replace_usage_scenario_variables,
                usage_scenario_variables=self._usage_scenario_variables,
                usage_scenario_file=usage_scenario_file,
            )

            if match := re.search(r'!include-gmt-helper gmt-playwright-(?:with-cache-)?(v\d+.\d+.\d+)\.yml', usage_scenario):
                self.__include_playwright_ipc_version = match[1]

            # We can use load here as the Loader extends SafeLoader
            yml_obj = yaml.load(usage_scenario, Loader)

            #Check that all variables have been replaced
            if matches := re.findall(r'^(?![\s]*#).*__GMT_VAR_\w+__', usage_scenario, re.MULTILINE):
                raise ValueError(f"Unreplaced leftover variables are still in usage_scenario: {matches}. \n\n {usage_scenario}. \n\n Please add variables when submitting run.")

            if len(self.__usage_scenario_variables_used_buffer) > 0:
                raise ValueError(f"Usage Scenario Variables '{self.__usage_scenario_variables_used_buffer}' was not used in usage scenario. Please remove it or add it to the usage scenario.")

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
                return dict2

            new_dict = {}

            if 'compose-file' in yml_obj.keys():
                for k,v in yml_obj['compose-file'].items():
                    if k in yml_obj:
                        new_dict[k] = merge_dicts(v,yml_obj[k])
                    else: # just copy over if no key exists in usage_scenario
                        yml_obj[k] = v
                del yml_obj['compose-file']

            yml_obj.update(new_dict)

            if 'flow-prepend' in yml_obj.keys():
                if not isinstance(yml_obj['flow-prepend'], list):
                    raise ValueError('magic key "flow-prepend" must be a list to be able to be processed as include')
                if 'flow' not in yml_obj:
                    yml_obj['flow'] = {} # flow might still be empty here. Only in syntax check after it must be non empty
                yml_obj['flow-prepend'].extend(yml_obj['flow'])
                yml_obj['flow'] = yml_obj['flow-prepend']
                del yml_obj['flow-prepend']


            # If a service is defined as None we remove it. This is so we can have a compose file that starts
            # all the various services but we can disable them in the usage_scenario. This is quite useful when
            # creating benchmarking scripts and you want to have all options in the compose but not in each benchmark.
            # The cleaner way would be to handle an empty service key throughout the code but would make it quite messy
            # so we chose to remove it right at the start.
            for key in [sname for sname, content in yml_obj.get('services', {}).items() if content is None]:
                del yml_obj['services'][key]

            self._usage_scenario = yml_obj

    def _initial_parse(self):

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

    def _prepare_docker(self):
        # Disable Docker CLI hints (e.g. "What's Next? ...")
        os.environ['DOCKER_CLI_HINTS'] = 'false'

    def _check_running_containers_before_start(self):
        result = subprocess.run(['docker', 'ps' ,'--format', '{{.Names}}'],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                check=True, encoding='UTF-8', errors='replace')
        for line in result.stdout.splitlines():
            for running_container in line.split(','): # if docker container has multiple tags, they will be split by comma, so we only want to
                for service_name in self._usage_scenario.get('services', {}):
                    if 'container_name' in self._usage_scenario['services'][service_name]:
                        container_name = self._usage_scenario['services'][service_name]['container_name']
                    else:
                        container_name = service_name

                    if running_container == container_name:
                        raise PermissionError(f"Container '{container_name}' is already running on system. Please close it before running the tool.")

    def _check_container_is_running(self, container_name: str, step_description: str, image_name: str | None = None):
        check_ps = subprocess.run(['docker', 'ps', '-q', '-f', f'name={container_name}'],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,
                                  check=False, encoding='UTF-8', errors='replace')
        if not check_ps.stdout.strip():
            # Container not running - this is an error condition that requires raising an exception
            logs_ps = subprocess.run(
                ['docker', 'logs', container_name],
                check=False,
                capture_output=True,
                encoding='UTF-8'
            )
            inspect_ps = subprocess.run(
                ['docker', 'inspect', '--format={{.State.ExitCode}}', container_name],
                check=False,
                capture_output=True,
                encoding='UTF-8'
            )
            exit_code = inspect_ps.stdout.strip() if inspect_ps.returncode == 0 else "unknown"

            if exit_code == "0":
                # Container exited with a successful exit code
                raise RuntimeError(f"Container '{container_name}' exited during {step_description} (exit code: {exit_code}). This indicates the container completed execution immediately (e.g., hello-world commands) or has configuration issues (invalid entrypoint, missing command).\nContainer logs:\n\n========== Stdout ==========\n{logs_ps.stdout}\n\n========== Stderr ==========\n{logs_ps.stderr}")
            else:
                # Container failed with non-zero or unknown exit code
                if not image_name:
                    image_ps = subprocess.run(
                        ['docker', 'inspect', '--format={{.Config.Image}}', container_name],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='UTF-8', errors='replace', check=False
                        )
                    if image_ps.returncode != 0:
                        raise RuntimeError(f"Container '{container_name}' failed during {step_description} but could not retrieve image information for architecture compatibility check. Docker inspect error: {image_ps.stderr.strip()}")
                    image_name = image_ps.stdout.strip()

                compatibility_info = container_compatibility.check_image_architecture_compatibility(image_name)
                compatibility_status = compatibility_info['status']

                if compatibility_status == CompatibilityStatus.INCOMPATIBLE:
                    raise RuntimeError(f"Container '{container_name}' failed during {step_description} due to architecture incompatibility (exit code: {exit_code}). Image architecture is '{compatibility_info['image_arch']}' but host architecture is '{compatibility_info['host_arch']}' and emulation is not available.\nContainer logs:\n\n========== Stdout ==========\n{logs_ps.stdout}\n\n========== Stderr ==========\n{logs_ps.stderr}")
                elif compatibility_status == CompatibilityStatus.EMULATED:
                    raise RuntimeError(f"Container '{container_name}' failed during {step_description}, possibly due to emulation issues (exit code: {exit_code}). Image architecture is '{compatibility_info['image_arch']}' but host architecture is '{compatibility_info['host_arch']}'. Container was running via emulation.\nContainer logs:\n\n========== Stdout ==========\n{logs_ps.stdout}\n\n========== Stderr ==========\n{logs_ps.stderr}")
                else:
                    raise RuntimeError(f"Container '{container_name}' failed during {step_description} (exit code: {exit_code}). This indicates startup issues such as missing dependencies, invalid entrypoints, or configuration problems.\nContainer logs:\n\n========== Stdout ==========\n{logs_ps.stdout}\n\n========== Stderr ==========\n{logs_ps.stderr}")

    def _check_running_containers_after_boot_phase(self):
        self._check_running_containers("boot phase")

    def _check_running_containers_after_runtime_phase(self):
        self._check_running_containers("runtime phase")

    def _check_running_containers(self, step_description: str):
        for container_info in self.__containers.values():
            self._check_container_is_running(container_info['name'], step_description)

    def _populate_image_names(self):
        for service_name, service in self._usage_scenario.get('services', {}).items():
            if not service.get('image', None): # image is a non-mandatory field. But we need it, so we tmp it
                if self._dev_cache_build:
                    service['image'] = f"{service_name}"
                else:
                    service['image'] = f"{service_name}_{random.randint(500000,10000000)}"

    def _remove_docker_images(self):
        print(TerminalColors.HEADER, '\nRemoving all temporary GMT images', TerminalColors.ENDC)

        config = GlobalConfig().config

        if self._dev_cache_build:
            print('Skipping removing of all temporary GMT images skipped due to --dev-cache-build')
            return

        subprocess.run(
            'docker images --format "{{.Repository}}:{{.Tag}}" | grep "gmt_run_tmp" | xargs docker rmi -f',
            shell=True,
            stderr=subprocess.DEVNULL, # to suppress showing of stderr
            check=False,
        )

        if self._full_docker_prune:
            print(TerminalColors.HEADER, '\nStopping and removing all containers, build caches, volumes and images on the system', TerminalColors.ENDC)
            subprocess.run('docker ps -aq | xargs docker stop', shell=True, check=False)

            docker_prune_images_cmd = 'docker images --format "{{.Repository}}:{{.Tag}} {{.ID}}"'
            for whitelisted_image in config['measurement']['full_docker_prune_whitelist']:
                docker_prune_images_cmd += f" | grep -v {shlex.quote(whitelisted_image)}"
            docker_prune_images_cmd += " | awk '{print $2}'"
            docker_prune_images_cmd += " | xargs docker rmi -f"
            subprocess.run(docker_prune_images_cmd, shell=True, check=False)

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
    def _register_machine_id(self):

        if self._dev_no_save:
            return

        config = GlobalConfig().config
        if config['machine'].get('id') is None \
            or not isinstance(config['machine']['id'], int) \
            or config['machine'].get('description') is None \
            or config['machine']['description'] == '':
            raise RuntimeError('You must set machine id and machine description')

        machine = Machine(machine_id=config['machine'].get('id'), description=config['machine'].get('description'))
        machine.register()

    def _initialize_run(self):
        print(TerminalColors.HEADER, '\nInitializing run', TerminalColors.ENDC)

        if self._dev_no_save:
            self._run_id = None
            print('Skipping initialization of run due to --dev-no-save')
            return self._run_id

        config = GlobalConfig().config

        gmt_hash, _ = get_repo_info(GMT_ROOT_DIR)

        # There are two ways we get hardware info. First things we don't need to be root to do which we get through
        # a method call. And then things we need root privilege which we need to call as a subprocess with sudo. The
        # install.sh script should have added the script to the sudoes file.
        machine_specs = hardware_info.get_default_values()

        if len(hardware_info_root.get_root_list()) > 0:
            ps = subprocess.run(['sudo', '/usr/bin/python3', '-m', 'lib.hardware_info_root'], stdout=subprocess.PIPE, cwd=GMT_ROOT_DIR, check=True, encoding='UTF-8', errors='replace')
            machine_specs_root = json.loads(ps.stdout)
            machine_specs.update(machine_specs_root)

        measurement_config = {}

        measurement_config['measurement_settings'] = {k: v for k, v in config['measurement'].items() if k != 'metric_providers'} # filter out static metric providers which might not be relevant for platform we are running on
        measurement_config['configured_metric_providers'] = utils.get_metric_providers(config, self._disabled_metric_providers) # get only the providers relevant to our platform
        measurement_config['cluster_settings'] = config.get('cluster', {}) # untypical that it is empty, but it does not necessarily need to exist
        measurement_config['machine_settings'] = config['machine']
        measurement_config['allowed_run_args'] = self._allowed_run_args
        measurement_config['disabled_metric_providers'] = self._disabled_metric_providers
        measurement_config['sci'] = self._sci
        measurement_config['phase_padding'] = self._phase_padding_ms

        # We issue a fetch_one() instead of a query() here, cause we want to get the RUN_ID
        self._run_id = DB().fetch_one("""
                INSERT INTO runs (
                    job_id, name, uri, branch, filename,
                    commit_hash, commit_timestamp, runner_arguments,
                    machine_specs, measurement_config,
                    usage_scenario, usage_scenario_variables, gmt_hash,
                    machine_id, user_id, created_at
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, NOW()
                )
                RETURNING id
                """, params=(
                    self._job_id, self._name, self._uri, self._branch, self._original_filename,
                    self._commit_hash, self._commit_timestamp, json.dumps(self._arguments),
                    json.dumps(machine_specs), json.dumps(measurement_config),
                    json.dumps(self._usage_scenario), json.dumps(self._usage_scenario_variables),
                    gmt_hash,
                    GlobalConfig().config['machine']['id'], self._user_id,
                ))[0]
        return self._run_id

    def _import_metric_providers(self):
        print(TerminalColors.HEADER, '\nImporting metric providers', TerminalColors.ENDC)

        if self._dev_no_metrics:
            print('Skipping import of metric providers due to --dev-no-save')
            return

        config = GlobalConfig().config


        metric_providers = utils.get_metric_providers(config)

        if not metric_providers:
            print(TerminalColors.WARNING, arrows('No metric providers were configured in config.yml. Was this intentional?'), TerminalColors.ENDC)
            return

        subprocess.run(["docker", "info"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, encoding='UTF-8', errors='replace', check=True)

        for metric_provider in metric_providers: # will iterate over keys
            module_path, class_name = metric_provider.rsplit('.', 1)
            module_path = f"metric_providers.{module_path}"
            conf = metric_providers[metric_provider] or {}

            if class_name in self._disabled_metric_providers:
                print(TerminalColors.WARNING, arrows(f"Not importing {class_name} as disabled per user settings"), TerminalColors.ENDC)
                continue

            print(f"Importing {class_name} from {module_path}")
            module = importlib.import_module(module_path)

            if self._skip_system_checks:
                metric_provider_obj = getattr(module, class_name)(**conf, skip_check=True)
                print(f"Configuration is {conf}; skip_check=true")
            else:
                metric_provider_obj = getattr(module, class_name)(**conf)
                print(f"Configuration is {conf}")




            self.__metric_providers.append(metric_provider_obj)

            if hasattr(metric_provider_obj, 'get_docker_params'):
                services_list = ",".join(list(self._usage_scenario.get('services', {}).keys()))
                self.__docker_params += metric_provider_obj.get_docker_params(no_proxy_list=services_list)


        self.__metric_providers.sort(key=lambda item: 'rapl' not in item.__class__.__name__.lower())

    def _download_dependencies(self):
        print(TerminalColors.HEADER, '\nDownloading dependencies', TerminalColors.ENDC)
        subprocess.run(['docker', 'pull', 'gcr.io/kaniko-project/executor:latest'], check=True)

    def _get_build_info(self, service):
        if isinstance(service['build'], str):
            # If build is a string we can assume the short form
            context = service['build']
            dockerfile = 'Dockerfile'
            args = {}
        else:
            context =  service['build'].get('context', '.')
            dockerfile = service['build'].get('dockerfile', 'Dockerfile')
            args = service['build'].get('args', {})

        return context, dockerfile, args

    def _clean_image_name(self, name):
        # clean up image name for problematic characters
        name = re.sub(r'[^A-Za-z0-9_]', '', name)
        # only lowercase letters are allowed for tags
        name = name.lower()
        name = f"{name}_gmt_run_tmp"
        return name

    def _build_docker_images(self):
        print(TerminalColors.HEADER, '\nBuilding Docker images', TerminalColors.ENDC)

        # Create directory /tmp/green-metrics-tool/docker_images
        temp_dir = f"{self._tmp_folder}/docker_images"
        self._initialize_folder(temp_dir)

        # technically the usage_scenario needs no services and can also operate on an empty list
        # This use case is when you have running containers on your host and want to benchmark some code running in them
        for _, service in self._usage_scenario.get('services', {}).items():
            # minimal protection from possible shell escapes.
            # since we use subprocess without shell we should be safe though
            if re.findall(r'(\.\.|\$|\'|"|`|!)', service['image']):
                raise ValueError(f"In scenario file the builds contains an invalid image name: {service['image']}")

            tmp_img_name = self._clean_image_name(service['image'])

            # If we are in developer repeat runs check if the docker image has already been built
            try:
                subprocess.run(['docker', 'inspect', '--type=image', tmp_img_name],
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE,
                                         encoding='UTF-8',
                                         errors='replace',
                                         check=True)
                # The image exists so exit and don't build
                print(f"Image {service['image']} exists in build cache. Skipping build ...")
                continue
            except subprocess.CalledProcessError:
                pass

            if 'build' in service:
                context, dockerfile, args = self._get_build_info(service)
                print(f"Building {service['image']}")
                self.__notes_helper.add_note( note=f"Building {service['image']}", detail_name='[NOTES]', timestamp=int(time.time_ns() / 1_000))

                # Make sure the context docker file exists and is not trying to escape some root. We don't need the returns
                context_path = self._join_paths(self.__working_folder, context)
                self._join_paths(context_path, dockerfile)

                repo_mount_path = service.get('folder-destination', '/tmp/repo')

                docker_build_command = ['docker', 'run', '--rm',
                    '-v', '/workspace',
                    # if we ever decide here to copy and not link in read-only we must NOT copy resolved symlinks, as they can be malicious
                    '-v', f"{self._repo_folder}:{repo_mount_path}:ro", # this is the folder where the usage_scenario is!
                    '-v', f"{temp_dir}:/output",
                    'gcr.io/kaniko-project/executor:latest',
                    f"--dockerfile={repo_mount_path}/{self.__working_folder_rel}/{context}/{dockerfile}",
                    '--context', f'dir://{repo_mount_path}/{self.__working_folder_rel}/{context}',
                    f"--destination={tmp_img_name}",
                    f"--tar-path=/output/{tmp_img_name}.tar",
                    '--cleanup=true',
                    '--no-push']

                for arg_dict in args:
                    for arg_key, arg_value in arg_dict.items():
                        docker_build_command.append(f"--build-arg={arg_key}={arg_value}")

                # docker agent might be configured to pull from a different, maybe even insecure registry
                # We want to mirror that behaviour in GMT as we see it used in specially configured environments
                # where custom docker registries are used
                docker_info = subprocess.check_output(['docker', 'info', '--format', '{{ json .RegistryConfig.Mirrors }}'], encoding='UTF-8', errors='replace')
                if docker_info and (mirrors := json.loads(docker_info)):
                    for mirror in mirrors:
                        if 'http://' in mirror:
                            mirror = mirror[7:]
                            docker_build_command.append('--registry-mirror')
                            docker_build_command.append(mirror)
                            docker_build_command.append('--insecure-pull')
                            docker_build_command.append('--insecure-registry')
                            docker_build_command.append(mirror)
                        else: # https
                            mirror = mirror[8:]
                            docker_build_command.append('--registry-mirror')
                            docker_build_command.append(mirror)

                if self.__docker_params:
                    docker_build_command[2:2] = self.__docker_params

                print(' '.join(docker_build_command))

                if self._measurement_total_duration:
                    ps = subprocess.run(docker_build_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='UTF-8', errors='replace', timeout=self._measurement_total_duration, check=False)
                else:
                    ps = subprocess.run(docker_build_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='UTF-8', errors='replace', check=False)

                if ps.returncode != 0:
                    raise subprocess.CalledProcessError(ps.returncode, 'Docker build failed', output=ps.stdout, stderr=ps.stderr)

                # import the docker image locally
                image_import_command = ['docker', 'load', '-q', '-i', f"{temp_dir}/{tmp_img_name}.tar"]
                print(' '.join(image_import_command))
                ps = subprocess.run(image_import_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='UTF-8', errors='replace', check=False)

                if ps.returncode != 0 or ps.stderr != "":
                    raise subprocess.CalledProcessError(ps.returncode, 'Docker image import failed', output=ps.stdout, stderr=ps.stderr)

            else:
                print(f"Pulling {service['image']}")
                self.__notes_helper.add_note( note=f"Pulling {service['image']}" , detail_name='[NOTES]', timestamp=int(time.time_ns() / 1_000))
                ps_pull = subprocess.run(['docker', 'pull', service['image']], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='UTF-8', errors='replace', check=False)

                if ps_pull.returncode != 0:
                    print(f"Error: {ps_pull.stderr} \n {ps_pull.stdout}")

                    # Check if it's an architecture mismatch error
                    stderr_lower = ps_pull.stderr.lower()
                    if "no matching manifest" in stderr_lower:
                        # This is definitely an architecture mismatch - create appropriate error
                        host_arch = container_compatibility.get_native_architecture()
                        raise RuntimeError(f"Architecture incompatibility detected: Docker image '{service['image']}' is not available for host architecture '{host_arch}'")

                    # Handle other Docker pull failures
                    if not sys.stdin.isatty():
                        raise subprocess.CalledProcessError(
                            ps_pull.returncode,
                            f"Docker pull failed. Is your image name correct and are you connected to the internet: {service['image']}",
                            output=ps_pull.stdout,
                            stderr=ps_pull.stderr
                        )
                    print(TerminalColors.OKCYAN, '\nThe docker image could not be pulled. Since you are working locally we can try looking in your local images. Do you want that? (y/N).', TerminalColors.ENDC)
                    if sys.stdin.readline().strip().lower() != 'y':
                        raise subprocess.CalledProcessError(
                            ps_pull.returncode,
                            f"Docker pull failed. Is your image name correct and are you connected to the internet: {service['image']}",
                            output=ps_pull.stdout,
                            stderr=ps_pull.stderr
                        )
                    ps_inpsect = subprocess.run(['docker', 'inspect', '--type=image', service['image']],
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         encoding='UTF-8',
                         errors='replace',
                         check=False)

                    if ps_inpsect.returncode != 0:
                        raise subprocess.CalledProcessError(
                            ps_pull.returncode, # still using original ps
                            f"Docker pull failed and image does not exist locally. Is your image name correct and are you connected to the internet: {service['image']}",
                            output=ps_pull.stdout,  # still using original ps
                            stderr=ps_pull.stderr) # still using original ps

                    print('Docker image found locally. Tagging now for use in cached runs ...')


                # tagging must be done in pull and local case, so we can get the correct container later
                subprocess.run(['docker', 'tag', service['image'], tmp_img_name], check=True)


        # Delete the directory /tmp/gmt_docker_images
        shutil.rmtree(temp_dir)

    def _save_image_and_volume_sizes(self):

        print(TerminalColors.HEADER, '\nSaving image and volume sizes', TerminalColors.ENDC)

        for _, service in self._usage_scenario.get('services', {}).items():
            tmp_img_name = self._clean_image_name(service['image'])

            # This will report bogus values on macOS sadly that do not align with "docker images" size info ...
            output = subprocess.check_output(
                f"docker image inspect {tmp_img_name} " + '--format={{.Size}}',
                shell=True,
                encoding='UTF-8',
                errors='replace',
            )
            self.__image_sizes[service['image']] = int(output.strip())

        # du -s -b does not work on macOS and also the docker image is in a VM and not accessible with du for us
        if not self._skip_volume_inspect and self._allow_unsafe and platform.system() != 'Darwin':
            for volume in self._usage_scenario.get('volumes', {}):
                # This will report bogus values on macOS sadly that do not align with "docker images" size info ...
                try:
                    output = subprocess.check_output(
                        ['docker', 'volume', 'inspect', volume, '--format={{.Mountpoint}}'],
                        encoding='UTF-8', errors='replace'
                    )
                    output = subprocess.check_output(
                        ['du', '-s', '-b', output.strip()],
                        encoding='UTF-8', errors='replace'
                    )

                    self.__volume_sizes[volume] = int(output.strip().split('\t', maxsplit=1)[0])
                except Exception as exc:
                    raise RuntimeError('Docker volumes could not be inspected. This can happen if you are storing images in a root only accessible location. Consider switching to docker rootless, running with --skip-volume-inspect or running GMT with sudo.') from exc

        if self._dev_no_save:
            print('Skipping saving of image and volume sizes due to --dev-no-save')
            return

        DB().query("""
            UPDATE runs
            SET machine_specs = machine_specs || %s
            WHERE id = %s
            """, params=(json.dumps({'Container Image Sizes': self.__image_sizes, 'Container Volume Sizes': self.__volume_sizes}), self._run_id))



    def _setup_networks(self):
        # for some rare containers there is no network, like machine learning for example
        if 'networks' in self._usage_scenario:
            print(TerminalColors.HEADER, '\nSetting up networks', TerminalColors.ENDC)
            for network in self._usage_scenario['networks']:
                if network in ('host', 'bridge', 'none'):
                    raise ValueError('Pre-defined networks like host, none and bridge cannot be created with Docker orchestrator. They already exist and can only be joined.')
                print('Creating network: ', network)
                # remove first if present to not get error, but do not make check=True, as this would lead to inf. loop
                subprocess.run(['docker', 'network', 'rm', network], stderr=subprocess.DEVNULL, check=False)

                if self._usage_scenario['networks'][network] and self._usage_scenario['networks'][network].get('internal', False):
                    subprocess.check_output(['docker', 'network', 'create', '--internal', network])
                else:
                    subprocess.check_output(['docker', 'network', 'create', network])

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

    def _order_services(self, services):
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

    def _setup_services(self):
        print(TerminalColors.HEADER, '\nSetting up services', TerminalColors.ENDC)
        # technically the usage_scenario needs no services and can also operate on an empty list
        # This use case is when you have running containers on your host and want to benchmark some code running in them
        services = self._usage_scenario.get('services', {})

        # Check if there are service dependencies defined with 'depends_on'.
        # If so, change the order of the services accordingly.
        services_ordered = self._order_services(services)
        for service_name, service in services_ordered.items():

            if 'container_name' in service:
                container_name = service['container_name']
            else:
                container_name = service_name

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

            repo_mount_path = service.get('folder-destination', '/tmp/repo')
            # if we ever decide here to copy and not link in read-only we must NOT copy resolved symlinks, as they can be malicious
            docker_run_string.append(f"{self._repo_folder}:{repo_mount_path}:ro")

            # this is a special feature container with a reserved name.
            # we only want to do the replacement when a magic include code was set, which is guaranteed via self.__include_playwright_ipc_version == True
            if self.__include_playwright_ipc_version and container_name == 'gmt-playwright-nodejs':
                docker_run_string.append('-v')
                docker_run_string.append(f"{GMT_ROOT_DIR}/templates/partials/gmt-playwright-ipc-{self.__include_playwright_ipc_version}.js:/tmp/gmt-utils/gmt-playwright-ipc-{self.__include_playwright_ipc_version}.js:ro")

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
                            path = self._join_paths(self.__working_folder, vol[0])
                        except FileNotFoundError as exc:
                            raise RuntimeError(f"The volume {vol[0]} could not be loaded or found at the specified path.") from exc
                        if len(vol) == 3:
                            if vol[2] != 'ro':
                                raise RuntimeError(f"Service '{service_name}': We only allow ro as parameter in volume mounts in unsafe mode")

                        docker_run_string.append('--mount')
                        docker_run_string.append(f"type=bind,source={path},target={vol[1]},readonly")

            if service.get('init', False):
                docker_run_string.append('--init')

            if shm_size := service.get('shm_size', False):
                docker_run_string.append('--shm-size')
                docker_run_string.append(str(shm_size))

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

            if 'docker-run-args' in service:
                for arg in service['docker-run-args']:
                    if self._allow_unsafe or any(re.fullmatch(allow_item, arg) for allow_item in self._allowed_run_args):
                        docker_run_string.extend(shlex.split(arg))
                    else:
                        raise RuntimeError(f"Argument '{arg}' is not allowed in the docker-run-args list. Please check the capabilities of the user or if running locally consider --allow-unsafe")


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
                    if not self._allow_unsafe and re.fullmatch(r'[A-Za-z_]+[A-Za-z0-9_]*', env_key) is None:
                        if self._skip_unsafe:
                            warn_message= arrows(f"Found environment var key with wrong format. Only ^[A-Za-z_]+[A-Za-z0-9_]*$ allowed: {env_key} - Skipping")
                            print(TerminalColors.WARNING, warn_message, TerminalColors.ENDC)
                            continue
                        env_var_check_errors.append(f"- key '{env_key}' has wrong format. Only ^[A-Za-z_]+[A-Za-z0-9_]*$ is allowed - Maybe consider using --allow-unsafe or --skip-unsafe")
                        continue # do not add to append string if not conformant

                    # Check the value of the environment var
                    # We only forbid long values (>1024), every character is allowed.
                    # The value is directly passed to the container and is not evaluated on the host system, so there is no security related reason to forbid special characters.
                    if not self._allow_unsafe and len(env_value) > 1024:
                        if self._skip_unsafe:
                            print(TerminalColors.WARNING, arrows(f"Found environment var value with size {len(env_value)} (max allowed length is 1024) - Skipping env var '{env_key}'"), TerminalColors.ENDC)
                            continue
                        env_var_check_errors.append(f"- value of environment var '{env_key}' is too long {len(env_value)} (max allowed length is 1024) - Maybe consider using --allow-unsafe or --skip-unsafe")
                        continue # do not add to append string if not conformant

                    docker_run_string.append('-e')
                    docker_run_string.append(f"{env_key}={env_value}")

                if env_var_check_errors:
                    raise RuntimeError('Docker container environment setup has problems:\n\n'.join(env_var_check_errors))

            if 'labels' in service:
                labels_check_errors = []
                for docker_label_var in service['labels']:
                    # https://docs.docker.com/reference/compose-file/services/#labels
                    if isinstance(docker_label_var, str) and '=' in docker_label_var:
                        label_key, label_value = docker_label_var.split('=')
                    elif isinstance(service['labels'], dict):
                        label_key, label_value = str(docker_label_var), str(service['labels'][docker_label_var])
                    else:
                        raise RuntimeError('Label needs to be a string with = or dict and non-empty. We do not allow the feature of forwarding variables from the host OS!')

                    # Check the key of the environment var
                    if not self._allow_unsafe and re.fullmatch(r'[A-Za-z_]+[A-Za-z0-9_.]*', label_key) is None:
                        if self._skip_unsafe:
                            warn_message= arrows(f"Found label key with wrong format. Only ^[A-Za-z_]+[A-Za-z0-9_.]*$ allowed: {label_key} - Skipping")
                            print(TerminalColors.WARNING, warn_message, TerminalColors.ENDC)
                            continue
                        labels_check_errors.append(f"- key '{label_key}' has wrong format. Only ^[A-Za-z_]+[A-Za-z0-9_.]*$ is allowed - Maybe consider using --allow-unsafe or --skip-unsafe")
                        continue # do not add to append string if not conformant

                    # Check the value of the environment var
                    # We only forbid long values (>1024), every character is allowed.
                    # The value is directly passed to the container and is not evaluated on the host system, so there is no security related reason to forbid special characters.
                    if not self._allow_unsafe and len(label_value) > 1024:
                        if self._skip_unsafe:
                            warn_message= arrows(f"Found label length > 1024: {label_key} - Skipping")
                            print(TerminalColors.WARNING, warn_message, TerminalColors.ENDC)
                            continue
                        labels_check_errors.append(f"- value of label '{label_key}' is too long {len(label_value)} (max allowed length is 1024) - Maybe consider using --allow-unsafe or --skip-unsafe")
                        continue # do not add to append string if not conformant

                    docker_run_string.append('-l')
                    docker_run_string.append(f"{label_key}={label_value}")

                if labels_check_errors:
                    raise RuntimeError('Docker container labels that have problems:\n\n'.join(labels_check_errors))

            if 'networks' in service:
                for network in service['networks']:
                    if network == 'host' and not self._allow_unsafe:
                        raise ValueError('Docker network host is restricted in GMT and cannot be joined. If running in CLI mode or if you have cluster capabilities try again with --allow-unsafe.')
                    docker_run_string.append('--net')
                    docker_run_string.append(network)
                    if isinstance(service['networks'], dict) and service['networks'][network]:
                        if service['networks'][network].get('aliases', None):
                            for alias in service['networks'][network]['aliases']:
                                if alias == 'host' and not self._allow_unsafe:
                                    raise ValueError('Docker network host is restricted in GMT and cannot be aliased. If running in CLI mode or if you have cluster capabilities try again with --allow-unsafe.')
                                docker_run_string.append('--network-alias')
                                docker_run_string.append(alias)
                                print(f"Adding network alias {alias} for network {network} in service {service_name}")

            elif self.__join_default_network:
                # only join default network if no other networks provided
                # if this is true only one entry is in self.__networks
                docker_run_string.append('--net')
                docker_run_string.append(self.__networks[0])


            if 'pause-after-phase' in service:
                self.__services_to_pause_phase[service['pause-after-phase']] = self.__services_to_pause_phase.get(service['pause-after-phase'], []) + [container_name]

            # wildly the docker compose spec allows deploy to be None ... thus we need to check and cannot .get()
            if 'deploy' in service and service['deploy'] is not None and (memory := service['deploy'].get('resources', {}).get('limits', {}).get('memory', None)):
                docker_run_string.append('--memory') # value in bytes
                docker_run_string.append(str(memory))
                print('Applying Memory Limit from deploy')
            elif memory := service.get('mem_limit', None): # we only need to get resources or cpus. they must align anyway
                docker_run_string.append('--memory')
                docker_run_string.append(str(memory))  # value in bytes e.g. "10M"
                print('Applying Memory Limit from services')

            if 'deploy' in service and service['deploy'] is not None and (cpus := service['deploy'].get('resources', {}).get('limits', {}).get('cpus', None)):
                docker_run_string.append('--cpus') # value in cores
                docker_run_string.append(str(cpus))
                print('Applying CPU Limit from deploy')
            elif cpus := service.get('cpus', None): # we only need to get resources or cpus. they must align anyway
                docker_run_string.append('--cpus')
                docker_run_string.append(str(cpus)) # value in (fractional) cores
                print('Applying CPU Limit from services')

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

            command_prepend = []

            if 'entrypoint' in service:
                if service['entrypoint']:
                    # If `entrypoint` is present and `command` we need to only supply the entrypoint as one long arg list
                    # please check https://github.com/green-coding-solutions/green-metrics-tool/issues/1100
                    # for a detailed discussion
                    docker_run_string.append('--entrypoint')

                    if isinstance(service['entrypoint'], list):
                        docker_run_string.append(service['entrypoint'][0])
                        command_prepend = service['entrypoint'][1:]

                    elif isinstance(service['entrypoint'], str):
                        entrypoint_list = shlex.split(service['entrypoint'])
                        docker_run_string.append(entrypoint_list[0])
                        command_prepend = entrypoint_list[1:]

                    else:
                        raise RuntimeError(f"Entrypoint in service '{service_name}' must be a string or a list but is: {type(service['entrypoint'])}")
                else:
                    # empty entrypoint -> default entrypoint will be ignored
                    docker_run_string.append('--entrypoint=')

            clean_image_name = self._clean_image_name(service['image'])

            # Architecture compatibility must be checked before docker run execution.
            # While docker pull has an architecture check, it only catches images with no
            # compatible manifest at all - the architecture of the used tag or hash digest
            # may still be incompatible.
            # Docker run exits with 0 even on incompatible architectures without '--platform',
            # requiring post-run checks with pauses to detect failures. Using '--platform'
            # prevents Docker emulation support, so we check compatibility upfront to fail
            # fast on incompatible images while allowing emulated execution when supported.
            print('Checking image architecture compatibility...')
            compatibility_info = container_compatibility.check_image_architecture_compatibility(clean_image_name)
            compatibility_status = compatibility_info['status']
            image_arch = compatibility_info['image_arch']
            host_arch = compatibility_info['host_arch']

            if compatibility_status == CompatibilityStatus.INCOMPATIBLE:
                # Image cannot run at all - fail immediately with clear error
                raise RuntimeError(f"Container '{container_name}' cannot run due to architecture incompatibility. Image architecture is '{image_arch}' but host architecture is '{host_arch}' and emulation is not available.")
            elif compatibility_status == CompatibilityStatus.EMULATED:
                # Image can run via emulation - add warning but allow Docker to handle it
                self.__warnings.append(f"Container '{container_name}' will run with architecture emulation. Image architecture is '{image_arch}' but host architecture is '{host_arch}'. This may impact performance.")
                print(f"Warning: Container will use emulation (image: {image_arch}, host: {host_arch})")
            elif compatibility_status == CompatibilityStatus.NATIVE:
                # Native compatibility - no action needed
                print(f"Architecture compatible: {image_arch} (native)")
            else:
                print('Architecture compatibility unknown. Trying run')

            docker_run_string.append(clean_image_name)

            # This is because only the first argument in the list is the command, the rest are arguments which need to come after
            # the service name but before the commands
            docker_run_string.extend(command_prepend)

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
                    max_waiting_time = self._measurement_wait_time_dependencies
                    while time_waited < max_waiting_time:
                        status_output = subprocess.check_output(
                            ["docker", "container", "inspect", "-f", "{{.State.Status}}", dependent_container_name],
                            stderr=subprocess.STDOUT,
                            encoding='UTF-8',
                            errors='replace'
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
                                    encoding='UTF-8',
                                    errors='replace'
                                )
                                health = ps.stdout.strip()
                                print(f"Container health of dependent service '{dependent_service}': {health}")

                                if ps.returncode != 0 or health == '<nil>':
                                    raise RuntimeError(f"Health check for service '{dependent_service}' was requested by '{service_name}', but service has no healthcheck implemented! (Output was: {health})")
                                if health == 'unhealthy':
                                    healthcheck_errors = subprocess.check_output(['docker', 'inspect', "--format={{json .State.Health}}", dependent_container_name], encoding='UTF-8', errors='replace')
                                    raise RuntimeError(f'Health check of container "{dependent_container_name}" failed terminally with status "unhealthy" after {time_waited}s. Health check errors: {healthcheck_errors}')
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
                        healthcheck_errors = subprocess.check_output(['docker', 'inspect', "--format={{json .State.Health}}", dependent_container_name], encoding='UTF-8', errors='replace')
                        raise RuntimeError(f"Health check of dependent services of '{service_name}' failed! Container '{dependent_container_name}' is not healthy but '{health}' after waiting for {time_waited} sec!\nHealth check errors: {healthcheck_errors}")



            if 'command' in service:  # must come last
                if isinstance(service['command'], str):
                    docker_run_string.extend(shlex.split(service['command']))
                elif isinstance(service['command'], list):
                    docker_run_string.extend(service['command'])
                else:
                    raise RuntimeError(f"Command in service '{service_name}' must be a string or a list but is: {type(service['command'])}")

            print(f"Running docker run with: {' '.join(docker_run_string)}")

            # docker_run_string must stay as list, cause this forces items to be quoted and escaped and prevents
            # injection of unwanted params

            ps = subprocess.run(
                docker_run_string,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='UTF-8',
                errors='replace'
            )

            if ps.returncode != 0:
                raise subprocess.CalledProcessError(
                            ps.returncode,
                            docker_run_string,
                            output=ps.stdout,
                            stderr=ps.stderr
                        )

            container_id = ps.stdout.strip()
            self.__containers[container_id] = {
                'name': container_name,
                'log-stdout': service.get('log-stdout', True),
                'log-stderr': service.get('log-stderr', True),
                'read-notes-stdout': service.get('read-notes-stdout', False),
                'read-sci-stdout': service.get('read-sci-stdout', False),
                'docker_run_cmd': docker_run_string,
            }

            print('Stdout:', container_id)

            print('Running commands')
            for cmd_obj in service.get('setup-commands', []):
                if shell := cmd_obj.get('shell', False):
                    d_command = ['docker', 'exec', container_name, shell, '-c', cmd_obj['command']] # This must be a list!
                else:
                    d_command = ['docker', 'exec', container_name, *shlex.split(cmd_obj['command'])] # This must be a list!

                print('Running command: ', ' '.join(d_command))

                if cmd_obj.get('detach', False) is True:
                    print('Executing setup-commands process asynchronously and detaching ...')
                    #pylint: disable=consider-using-with,subprocess-popen-preexec-fn
                    # docker exec must stay as list, cause this forces items to be quoted and escaped and prevents
                    # injection of unwawnted params

                    ps = subprocess.Popen(
                        d_command,
                        stderr=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        preexec_fn=os.setsid,
                        encoding='UTF-8',
                        errors='replace',
                    )

                    self.__ps_to_kill.append({'ps': ps, 'cmd': cmd_obj['command'], 'ps_group': False})

                else:
                    # docker exec must stay as list, cause this forces items to be quoted and escaped and prevents
                    # injection of unwawnted params
                    ps = subprocess.run(
                        d_command,
                        check=False,
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        encoding='UTF-8',
                        errors='replace',
                    )

                    if ps.returncode != 0:
                        raise RuntimeError(f"Process {d_command} failed.\n\n========== Stdout ==========\n{ps.stdout}\n\n========== Stderr ==========\n{ps.stderr}")

                self.__ps_to_read.append({
                    'cmd': d_command,
                    'ps': ps,
                    'container_name': container_name,
                    'read-notes-stdout': cmd_obj.get('read-notes-stdout', False),
                    'ignore-errors': cmd_obj.get('ignore-errors', False),
                    'read-sci-stdout': cmd_obj.get('read-sci-stdout', False),
                    'detail_name': container_name,
                    'detach': cmd_obj.get('detach', False),
                })

        container_names = [container_info['name'] for container_info in self.__containers.values()]
        print(TerminalColors.HEADER, '\nStarted containers: ', container_names, TerminalColors.ENDC)


    def _add_to_current_run_log(self, container_name, log_type, log_id, cmd, phase, stdout=None, stderr=None, flow=None, exception_class=None):
        if container_name not in self.__current_run_logs:
            self.__current_run_logs[container_name] = []

        command_string = ' '.join(cmd) if isinstance(cmd, list) else str(cmd)

        log_entry = {
            'type': log_type.value,
            'id': str(log_id),
            'cmd': command_string,
            'phase': phase
        }

        if stdout is not None:
            log_entry['stdout'] = stdout.replace('\x00', '0x00') # Postgres cannot handle null bytes (\x00) in text fields or \u0000 in JSONB columns
        if stderr is not None:
            log_entry['stderr'] = stderr.replace('\x00', '0x00') # Postgres cannot handle null bytes (\x00) in text fields or \u0000 in JSONB columns
        if flow is not None:
            log_entry['flow'] = flow
        if exception_class is not None:
            log_entry['exception_class'] = exception_class

        self.__current_run_logs[container_name].append(log_entry)


    '''
        Returns accumulated logs from all runs in the current session.

        This method provides read-only access to logs collected across multiple runs
        when using --iterations > 1 or multiple filenames. Each run's logs are preserved
        and accumulated to support the --print-logs functionality.

        Returns:
            list: All log entries from current session in enhanced structure.
                  Each list item is a run object containing:
                    - 'iteration': iteration number for this filename
                    - 'filename': the scenario filename that was executed
                    - 'containers': dict with container names as keys and log lists as values
    '''
    def _get_all_run_logs(self):
        return self.__all_runs_logs

    def _save_warnings(self):
        if not self._run_id or self._dev_no_save:
            print("Skipping saving warning due to missing run id or --dev-no-save")
            return
        for message in self.__warnings:
            DB().query("INSERT INTO warnings (run_id, message) VALUES (%s, %s)", (self._run_id, message))


    def _execute_dependency_resolving_for_container(self, container_name):
        try:
            start_time = time.perf_counter()

            result = resolve_docker_dependencies_as_dict(
                container_identifier=container_name
            )

            duration = time.perf_counter() - start_time

            # Count total packages found across all package managers
            total_packages = 0
            if result:
                for key, value in result.items():
                    if key != 'source' and isinstance(value, dict):
                        if 'dependencies' in value:
                            total_packages += len(value['dependencies'])
                        elif 'locations' in value:
                            # Handle mixed-scope with multiple locations (e.g., pip)
                            for location_data in value['locations'].values():
                                if 'dependencies' in location_data:
                                    total_packages += len(location_data['dependencies'])

            print(f"Dependency resolution for container '{container_name}' found {total_packages} packages in {duration:.2f} s")

            # Remove the 'name' field from source as we use container name as key
            if result and 'name' in result.get('source', {}):
                del result['source']['name']

            return container_name, result if result else None

        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"Error executing energy-dependency-inspector for container {container_name}: {exc}")
            return container_name, None

    def _collect_container_dependencies(self):
        """Wrapper method to collect container dependencies."""
        self._collect_dependency_info()

        if self._run_id:
            DB().query("""
                UPDATE runs
                SET usage_scenario_dependencies = %s
                WHERE id = %s
                """, params=(json.dumps(self.__usage_scenario_dependencies) if self.__usage_scenario_dependencies is not None else None, self._run_id))

    def _collect_dependency_info(self):
        """Collect dependency information for all containers."""
        if not self.__containers:
            print("No containers available for dependency resolution")
            return

        print(TerminalColors.HEADER, '\nCollecting dependency information', TerminalColors.ENDC)
        container_names = [container_info['name'] for container_info in self.__containers.values()]

        # Execute energy-dependency-inspector for all containers in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(len(container_names), 4)) as executor:
            results = list(executor.map(self._execute_dependency_resolving_for_container, container_names))

        # Process results - abort on any failure
        # Each result is either: (container_name, container_info), (container_name, None), or Exception
        container_dependencies = {}
        for result in results:
            if isinstance(result, tuple) and result[1] is not None:
                container_name, container_info = result
                container_dependencies[container_name] = container_info
            elif isinstance(result, Exception):
                raise RuntimeError(f"Dependency resolution failed: {result}. Aborting GMT run.")
            else:
                # Dependency resolution failed for this container
                container_name = result[0] if isinstance(result, tuple) else "unknown"
                raise RuntimeError(f"Dependency resolution failed for container '{container_name}'. Aborting GMT run.")

        if container_dependencies:
            self.__usage_scenario_dependencies = container_dependencies
        else:
            raise RuntimeError("No dependency information collected. This indicates no containers were processed or all dependency resolution attempts failed.")

    def _add_containers_to_metric_providers(self):
        for metric_provider in self.__metric_providers:
            if metric_provider._metric_name.endswith('_container'):
                metric_provider.add_containers(self.__containers)

    def _start_metric_providers(self, allow_container=True, allow_other=True):
        print(TerminalColors.HEADER, '\nStarting metric providers', TerminalColors.ENDC)

        if self._dev_no_metrics:
            print('Skipping start of metric providers due to --dev-no-metrics')
            return


        # Here we start all container related providers
        # This includes tcpdump, which is only for debugging of the containers itself
        # If debugging of the tool itself is wanted tcpdump should be started adjacent to the tool and not inline
        for metric_provider in self.__metric_providers:
            if (metric_provider._metric_name.endswith('_container') or metric_provider._metric_name == 'network_connections_tcpdump_system' ) and not allow_container:
                continue

            if not metric_provider._metric_name.endswith('_container') and metric_provider._metric_name != 'network_connections_tcpdump_system' and not allow_other:
                continue

            if metric_provider.has_started():
                raise RuntimeError(f"Metric provider {metric_provider.__class__.__name__} was already started!")

            message = f"Booting {metric_provider.__class__.__name__}"
            metric_provider.start_profiling()

            if self._verbose_provider_boot:
                self.__notes_helper.add_note( note=message, detail_name='[NOTES]', timestamp=int(time.time_ns() / 1_000))
                self._custom_sleep(10)

        print(TerminalColors.HEADER, '\nWaiting for Metric Providers to boot ...', TerminalColors.ENDC)
        # if this is omitted the stderr can be empty even if the process is not found by the OS ... python process spawning is slow ...
        self._custom_sleep(2)

        for metric_provider in self.__metric_providers:
            if (metric_provider._metric_name.endswith('_container') or metric_provider._metric_name == 'network_connections_tcpdump_system' ) and not allow_container:
                continue

            if not metric_provider._metric_name.endswith('_container') and metric_provider._metric_name != 'network_connections_tcpdump_system' and not allow_other:
                continue

            stderr_read = metric_provider.get_stderr()
            print(f"Stderr check on {metric_provider.__class__.__name__}")

            if stderr_read:
                raise RuntimeError(f"Stderr on {metric_provider.__class__.__name__} was NOT empty: {stderr_read}")

    def _check_total_runtime_exceeded(self):
        if self._measurement_total_duration and (time.time() - self.__start_measurement_seconds) > self._measurement_total_duration:
            raise TimeoutError(f"Timeout of {self._measurement_total_duration} s was exceeded. This can be configured in the user authentication for 'total_duration'.")

    def _start_phase(self, phase, *, hidden=False, transition=True):
        print(TerminalColors.HEADER, f"\nStarting phase {phase}.", TerminalColors.ENDC)

        self._check_total_runtime_exceeded()

        if transition:
            # The force-sleep must go and we must actually check for the temperature baseline
            print(f"\nForce-sleeping for {self._measurement_phase_transition_time}s")
            self._custom_sleep(self._measurement_phase_transition_time)
            #print(TerminalColors.HEADER, '\nChecking if temperature is back to baseline ...', TerminalColors.ENDC)

        phase_time = int(time.time_ns() / 1_000)
        self.__notes_helper.add_note( note=f"Starting phase {phase}", detail_name='[NOTES]', timestamp=phase_time)

        self.__phases[phase] = {'start': phase_time, 'name': phase, 'hidden': hidden}

    def _end_phase(self, phase):

        self._check_total_runtime_exceeded()

        phase_time = int(time.time_ns() / 1_000)

        if self._phase_padding:
            self.__notes_helper.add_note( note=f"Ending phase {phase} [UNPADDED]", detail_name='[NOTES]', timestamp=phase_time)
            phase_time += self._phase_padding_ms*1000 # value is in ms and we need to get to us
            time.sleep(self._phase_padding_ms/1000) # no custom sleep here as even with dev_no_sleeps we must ensure phases don't overlap

        if phase not in self.__phases:
            raise RuntimeError(f'Phase "{phase}" not found in known phases: "{list(self.__phases.keys())}". '
                              f'This could indicate calling end_phase before start_phase or an invalid phase name. '
                              f'This is a developer error!')

        if phase in self.__services_to_pause_phase:
            for container_to_pause in self.__services_to_pause_phase[phase]:
                info_text = f"Pausing {container_to_pause} after phase: {phase}."
                print(info_text)
                self.__notes_helper.add_note( note= info_text, detail_name='[NOTES]', timestamp=phase_time)

                subprocess.run(['docker', 'pause', container_to_pause], check=True, stdout=subprocess.DEVNULL)

        self.__phases[phase]['end'] = phase_time

        if self._phase_padding:
            self.__notes_helper.add_note( note=f"Ending phase {phase} [PADDED]", detail_name='[NOTES]', timestamp=phase_time)
        else:
            self.__notes_helper.add_note( note=f"Ending phase {phase} [UNPADDED]", detail_name='[NOTES]', timestamp=phase_time)

    def _run_flows(self):
        ps_to_kill_tmp = []
        ps_to_read_tmp = []
        flow_id = 0
        flows_len = len(self._usage_scenario['flow'])

        while flow_id < flows_len:
            flow = self._usage_scenario['flow'][flow_id]
            ps_to_kill_tmp.clear()
            ps_to_read_tmp.clear()

            print(TerminalColors.HEADER, '\nRunning flow: ', flow['name'], TerminalColors.ENDC)

            try:
                self._start_phase(flow['name'], hidden=flow.get('hidden', False), transition=False)

                for cmd_obj in flow['commands']:
                    self._check_total_runtime_exceeded()

                    if 'note' in cmd_obj:
                        self.__notes_helper.add_note( note=cmd_obj['note'], detail_name=flow['container'], timestamp=int(time.time_ns() / 1_000))

                    print(TerminalColors.HEADER, '\n', cmd_obj['type'], 'command:', cmd_obj['command'], 'on container', flow['container'], TerminalColors.ENDC)

                    docker_exec_command = ['docker', 'exec']
                    docker_exec_command.append(flow['container'])
                    stderr_behaviour = stdout_behaviour = subprocess.DEVNULL
                    if cmd_obj.get('stream-stdout', False):
                        stdout_behaviour = None
                        self.__warnings.append('Stdout for a command was be streamed. This can create significant overhead and also means it cannot be captured to the logs. Only use this in local development')
                    elif cmd_obj.get('log-stdout', True):
                        stdout_behaviour = subprocess.PIPE
                    if cmd_obj.get('stream-stderr', False):
                        stderr_behaviour = None
                        self.__warnings.append('Stderr for a command was be streamed. This can create significant overhead and also means it cannot be captured to the logs. Only use this in local development')
                    if cmd_obj.get('log-stderr', True):
                        stderr_behaviour = subprocess.PIPE

                    if cmd_obj['type'] == 'playwright':
                        docker_exec_command.append(cmd_obj.get('shell', 'sh'))
                        docker_exec_command.append('-c')
                        escaped_command = cmd_obj['command'].replace("'", "\\'")
                        docker_exec_command.append(f"echo '{escaped_command}' > /tmp/playwright-ipc-commands")

                    elif cmd_obj['type'] == 'console':

                        if shell := cmd_obj.get('shell', False):
                            docker_exec_command.append(shell)
                            docker_exec_command.append('-c')
                            docker_exec_command.append(cmd_obj['command'])
                        else:
                            docker_exec_command.extend(shlex.split(cmd_obj['command']))
                    else:
                        raise RuntimeError('Unknown command type in flow: ', cmd_obj['type'])


                    if cmd_obj.get('detach', False) is True and cmd_obj['type'] == 'playwright':
                        raise ValueError('Playwright commands cannot be executed detached, as they must be awaited')
                    elif cmd_obj.get('detach', False) is True:
                        print('Executing process asynchronously and detaching ...')
                        # Note: In case of a detach wish in the usage_scenario.yml:
                        # We are NOT using the -d flag from docker exec, as this prohibits getting the stdout.
                        # Since Popen always make the process asynchronous we can leverage this to emulate a detached behavior

                        #pylint: disable=consider-using-with,subprocess-popen-preexec-fn
                        ps = subprocess.Popen(
                            docker_exec_command,
                            stderr=stderr_behaviour,
                            stdout=stdout_behaviour,
                            preexec_fn=os.setsid,
                            encoding='UTF-8',
                            errors='replace',
                        )
                        if stderr_behaviour == subprocess.PIPE:
                            os.set_blocking(ps.stderr.fileno(), False)
                        if  stdout_behaviour == subprocess.PIPE:
                            os.set_blocking(ps.stdout.fileno(), False)

                        ps_to_kill_tmp.append({'ps': ps, 'cmd': cmd_obj['command'], 'ps_group': False})
                    else:
                        print('Executing process synchronously.')
                        if self._measurement_flow_process_duration:
                            print(f"Alloting {self._measurement_flow_process_duration}s runtime ...")

                        ps = subprocess.run(
                            docker_exec_command,
                            stderr=stderr_behaviour,
                            stdout=stdout_behaviour,
                            encoding='UTF-8',
                            errors='replace',
                            check=False, # cause it will be checked later and also ignore-errors checked
                            timeout=self._measurement_flow_process_duration,
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
                        'flow_name': flow['name'],
                    })

                    # we need to check the ready IPC endpoint to find out if the process is done
                    # this command will block until something is received
                    if cmd_obj['type'] == 'playwright':
                        print("Awaiting Playwright function return")
                        ps = subprocess.run(
                            ['docker', 'exec', flow['container'], 'cat', '/tmp/playwright-ipc-ready'],
                            check=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            encoding='UTF-8',
                            errors='replace',
                            timeout=60, # 60 seconds should be reasonable for any playwright command we know
                        )


                    if self._debugger.active:
                        self._debugger.pause('Waiting to start next command in flow')

                self._end_phase(flow['name'])
                self.__ps_to_kill += ps_to_kill_tmp
                self.__ps_to_read += ps_to_read_tmp # will otherwise be discarded, bc they confuse execption handling
                self._check_process_returncodes()

            # pylint: disable=broad-exception-caught
            except BaseException as flow_exc:
                if not self._dev_flow_timetravel: # Exception handling only if explicitely wanted
                    raise flow_exc
                if self.__phases[flow['name']].get('end', None) is None:
                    self._end_phase(flow['name']) # force end phase if exception happened before ending phase
                print('Exception occured: ', flow_exc)
            finally:
                flow_id += 1 # advance flow counter in any case

            if not self._dev_flow_timetravel: # Timetravel only if active
                continue

            print(TerminalColors.OKCYAN, '\nTime Travel mode is active!\nWhat do you want to do?\n')
            print('0 -- Continue\n1 -- Restart current flow\n2 -- Restart all flows\n')
            print('Note: Process logging, SCI calculations, and notes extraction may be incomplete in timetravel mode\n')
            print('9 / CTRL+C -- Abort', TerminalColors.ENDC)

            def cleanup_processes():
                self.__ps_to_read.clear() # clear old processes - may cause incomplete logging, SCI, and notes results
                for ps in ps_to_kill_tmp:
                    print(f"Trying to kill detached process '{ps['cmd']}'' of current flow")
                    try:
                        process_helpers.kill_pg(ps['ps'], ps['cmd'])
                    except ProcessLookupError as process_exc: # Process might have done expected exit already. However all other errors shall bubble
                        print(f"Could not kill {ps['cmd']}. Exception: {process_exc}")

            while True:
                value = sys.stdin.readline().strip()

                if value == '0':
                    break
                elif value == '1':
                    cleanup_processes()
                    self.__phases.popitem(last=True)
                    flow_id -= 1
                    break
                elif value == '2':
                    cleanup_processes()
                    for _ in range(0,flow_id):
                        self.__phases.popitem(last=True)
                    flow_id = 0
                    break
                elif value == '9':
                    raise KeyboardInterrupt("Manual abort")
                else:
                    print(TerminalColors.OKCYAN, 'Did not understand input. Please type a valid number ...', TerminalColors.ENDC)

    # this method should never be called twice to avoid double logging of metrics
    def _stop_metric_providers(self):
        print(TerminalColors.HEADER, 'Stopping metric providers and parsing measurements', TerminalColors.ENDC)

        if self._dev_no_metrics:
            print('Skipping stop of metric providers due to --dev-no-metrics')
            return

        errors = []
        for metric_provider in self.__metric_providers:
            if not metric_provider.has_started():
                continue

            stderr_read = metric_provider.get_stderr()
            if stderr_read:
                errors.append(f"Stderr on {metric_provider.__class__.__name__} was NOT empty: {stderr_read}")

            # pylint: disable=broad-exception-caught
            # we definitely want to first try to stop all providers and then fail
            try:
                metric_provider.stop_profiling()
            except Exception as exc:
                errors.append(f"Could not stop profiling on {metric_provider.__class__.__name__}: {str(exc)}")

            try:
                df = metric_provider.read_metrics()
            except RuntimeError as exc:
                errors.append(f"{metric_provider.__class__.__name__} returned error message: {str(exc)}")
                continue

            if self._dev_no_save:
                print('Skipping import of metrics from provider due to --dev-no-save')
                continue

            if isinstance(df, list):
                for i, dfi in enumerate(df):
                    metric_importer.import_measurements(dfi, metric_provider._sub_metrics_name[i], self._run_id)
            else:
                metric_importer.import_measurements(df, metric_provider._metric_name, self._run_id)

            print('Imported', TerminalColors.HEADER, len(df), TerminalColors.ENDC, 'metrics from ', metric_provider.__class__.__name__)

        self.__metric_providers.clear()
        if errors:
            raise RuntimeError("\n".join(errors))

    def _handle_process_output(self, stdout, stderr, container_name, log_type,
                              log_id, cmd, phase, flow=None,
                              read_notes_stdout=False, read_sci_stdout=False,
                              detail_name=None):
        # Only create log entries if there's actual content
        has_stdout = stdout is not None and stdout.strip()
        has_stderr = stderr is not None and stderr.strip()

        if has_stdout or has_stderr:
            if has_stdout and log_type != LogType.CONTAINER_EXECUTION:
                print('stdout from process:', cmd, stdout)
            if has_stderr and log_type != LogType.CONTAINER_EXECUTION:
                print('stderr from process:', cmd, stderr)

            self._add_to_current_run_log(
                container_name=container_name,
                log_type=log_type,
                log_id=log_id,
                cmd=cmd,
                phase=phase,
                stdout=stdout if has_stdout else None,
                stderr=stderr if has_stderr else None,
                flow=flow
            )

            if has_stdout and read_notes_stdout:
                self.__notes_helper.parse_and_add_notes(detail_name or container_name, stdout)

            if has_stdout and read_sci_stdout:
                for match in re.findall(r'^GMT_SCI_R=(\d+)$', stdout, re.MULTILINE):
                    self._sci['R'] += int(match)

    def _read_and_cleanup_processes(self):
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

            log_type = LogType.FLOW_COMMAND if ps.get('flow_name') else LogType.SETUP_COMMAND
            match log_type:
                case LogType.FLOW_COMMAND:
                    phase = '[RUNTIME]'
                case LogType.SETUP_COMMAND:
                    phase = '[BOOT]'
                case _:
                    phase = '[UNKNOWN]'

            self._handle_process_output(
                stdout=stdout,
                stderr=stderr,
                container_name=ps['container_name'],
                log_type=log_type,
                log_id=id(ps['ps']),
                cmd=ps['cmd'],
                phase=phase,
                flow=ps.get('flow_name'),
                read_notes_stdout=ps['read-notes-stdout'],
                read_sci_stdout=ps['read-sci-stdout'],
                detail_name=ps['detail_name']
            )

    def _check_process_returncodes(self):
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

    def _start_measurement(self):
        self.__start_measurement = int(time.time_ns() / 1_000)
        self.__start_measurement_seconds = time.time()

        self.__notes_helper.add_note( note='Start of measurement', detail_name='[NOTES]', timestamp=self.__start_measurement)

    def _end_measurement(self, skip_on_already_ended=False):
        if self.__end_measurement:
            if skip_on_already_ended:
                return
            raise RuntimeError('end_measurement was requested although value as already set!')

        self.__end_measurement = int(time.time_ns() / 1_000)
        self.__notes_helper.add_note( note='End of measurement', detail_name='[NOTES]', timestamp=self.__end_measurement)

        self._update_start_and_end_times()

    def _update_start_and_end_times(self):
        print(TerminalColors.HEADER, '\nUpdating start and end measurement times', TerminalColors.ENDC)

        if not self._run_id or self._dev_no_save:
            print('Skipping update of start and end times due to missing run id or --dev-no-save')
            return # Nothing to do, but also no hard error needed

        DB().query("""
            UPDATE runs
            SET start_measurement=%s, end_measurement=%s
            WHERE id = %s
            """, params=(self.__start_measurement, self.__end_measurement, self._run_id))
        self._last_measurement_duration = self.__end_measurement - self.__start_measurement


    def _set_run_failed(self):
        print(TerminalColors.HEADER, '\nMarking run as failed', TerminalColors.ENDC)

        if not self._run_id or self._dev_no_save:
            print('Skipping marking run to failed due to missing run id or --dev-no-save')
            return # Nothing to do, but also no hard error needed

        DB().query("""
            UPDATE runs
            SET failed = TRUE
            WHERE id = %s
            """, params=(self._run_id, ))


    def _store_phases(self):
        print(TerminalColors.HEADER, '\nUpdating phases in DB', TerminalColors.ENDC)

        if not self._run_id or self._dev_no_save:
            print('Skipping updating phases in DB due to missing run id or --dev-no-save')
            return # Nothing to do, but also no hard error needed

        # internally PostgreSQL stores JSON ordered. This means our name-indexed dict will get
        # re-ordered. Therefore we change the structure and make it a list now.
        # We did not make this before, as we needed the duplicate checking of dicts
        phases = list(self.__phases.values())
        DB().query("""
            UPDATE runs
            SET phases=%s
            WHERE id = %s
            """, params=(json.dumps(phases), self._run_id))

    def _read_container_logs(self):
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
                errors='replace',
                stdout=stdout_behaviour,
                stderr=stderr_behaviour,
            )

            self._handle_process_output(
                stdout=log.stdout,
                stderr=log.stderr,
                container_name=container_info['name'],
                log_type=LogType.CONTAINER_EXECUTION,
                log_id=id(log),
                cmd=container_info['docker_run_cmd'],
                phase='[MULTIPLE]', # the container logs were collected usually over multiple phases: [BOOT], [IDLE], [RUNTIME]
                read_notes_stdout=container_info['read-notes-stdout'],
                read_sci_stdout=container_info['read-sci-stdout']
            )

    def _save_run_logs(self):
        print(TerminalColors.HEADER, '\nSaving logs to DB', TerminalColors.ENDC)

        if not self._run_id or self._dev_no_save:
            print('Skipping savings logs to DB due to missing run id or --dev-no-save')
            return # Nothing to do, but also no hard error needed

        if self.__current_run_logs:
            logs_as_json = json.dumps(self.__current_run_logs, separators=(',', ':'))  # Compact JSON for efficient storage
            DB().query("""
                UPDATE runs
                SET logs = COALESCE(logs, '{}'::jsonb) || %s::jsonb
                WHERE id = %s
                """, params=(logs_as_json, self._run_id))


    # This function will be extended in the future to have more conditions
    # Possible could be:
    #    - Temperature has gotten too high
    #    - Turbo Boost became active during run
    #    - etc.
    def _identify_invalid_run(self):
        print(TerminalColors.HEADER, '\nTrying to identify if run is invalid', TerminalColors.ENDC)

        # on macOS we run our tests inside the VM. Thus measurements are not reliable as they contain the overhead and reproducability is quite bad.
        if platform.system() == 'Darwin':
            invalid_message = 'Measurements are not reliable as they are done on a Mac in a virtualized docker environment with high overhead and low reproducability.\n'
            print(TerminalColors.WARNING, invalid_message, TerminalColors.ENDC)

            if not self._run_id or self._dev_no_save:
                print(TerminalColors.WARNING, '\nSkipping saving identification if run is invalid due to missing run id or --dev-no-save', TerminalColors.ENDC)
            else:
                self.__warnings.append(invalid_message)

        for argument in self._arguments:
            # dev no optimizations does not make the run invalid ... all others do
            if argument != 'dev_no_optimizations' and (argument.startswith('dev_') or argument == 'skip_system_checks')  and self._arguments[argument] not in (False, None):
                invalid_message = 'Development switches or skip_system_checks were active for this run. This will likely produce skewed measurement data.\n'
                print(TerminalColors.WARNING, invalid_message, TerminalColors.ENDC)

                if not self._run_id or self._dev_no_save:
                    print(TerminalColors.WARNING, '\nSkipping saving identification if run is invalid due to missing run id or --dev-no-save', TerminalColors.ENDC)
                else:
                    self.__warnings.append(invalid_message)
                break # one is enough

    def _patch_phases(self):
        if self.__phases:
            last_phase_name, _ = next(reversed(self.__phases.items()))
            if self.__phases[last_phase_name].get('end', None) is None:
                self.__phases[last_phase_name]['end'] = int(time.time_ns() / 1_000)

            # Also patch Runtime phase separately, which we need as this will only get set after all child runtime phases
            if self.__phases.get('[RUNTIME]', None) is not None and self.__phases['[RUNTIME]'].get('end', None) is None:
                self.__phases['[RUNTIME]']['end'] = int(time.time_ns() / 1_000)

    def _process_phase_stats(self):
        if not self._run_id or self._dev_no_phase_stats or self._dev_no_metrics or self._dev_no_save:
            return

        # After every run, even if it failed, we want to generate phase stats.
        # They will not show the accurate data, but they are still neded to understand how
        # much a failed run has accrued in total energy and carbon costs
        print(TerminalColors.HEADER, '\nCalculating and storing phases data. This can take a couple of seconds ...', TerminalColors.ENDC)

        # get all the metrics from the measurements table grouped by metric
        # loop over them issuing separate queries to the DB
        from tools.phase_stats import build_and_store_phase_stats # pylint: disable=import-outside-toplevel
        build_and_store_phase_stats(self._run_id, self._sci)

    def _post_process(self, index):
        try:
            for step in self._safe_post_processing_steps[index:]:
                method_name, args = step
                getattr(self, method_name)(**args)
                index += 1
        except BaseException as exc:
            self._add_to_current_run_log(
                container_name='[SYSTEM]',
                log_type=LogType.EXCEPTION,
                log_id=id(exc),
                cmd='post_process',
                phase='[CLEANUP]',
                stderr=f"{str(exc)}\n\n{exc.stderr}" if hasattr(exc, 'stderr') else str(exc),
                stdout=exc.stdout if hasattr(exc, 'stdout') else None,
                exception_class=exc.__class__.__name__
            )
            self._set_run_failed()
            self._post_process(index+1)
            raise exc

    def cleanup(self):
        """Clean up all resources including containers, networks, processes, and metric providers."""
        print(TerminalColors.OKCYAN, '\nStarting cleanup routine', TerminalColors.ENDC)

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
        self.__containers.clear()

        print('Removing network')
        for network_name in self.__networks:
            # no check=True, as the network might already be gone. We do not want to fail here
            subprocess.run(['docker', 'network', 'rm', network_name], stderr=subprocess.DEVNULL, check=False)
        self.__networks.clear()

        self._remove_docker_images()

        for ps in self.__ps_to_kill:
            try:
                process_helpers.kill_pg(ps['ps'], ps['cmd'])
            except ProcessLookupError as exc: # Process might have done expected exit already. However all other errors shall bubble
                print(f"Could not kill {ps['cmd']}. Exception: {exc}")

        self.__ps_to_kill.clear()
        self.__ps_to_read.clear()

        self.__start_measurement = None
        self.__start_measurement_seconds = None
        self.__notes_helper = Notes()

        # Store current run in cumulative logs with iteration and filename tracking
        # All runs are tracked regardless of log generation for consistent --print-logs output
        filename = self._original_filename
        iteration = 1
        for existing_run in self.__all_runs_logs:
            if existing_run['filename'] == filename:
                iteration = max(iteration, existing_run['iteration'] + 1)

        run_entry = {
            'iteration': iteration,
            'filename': filename,
            'containers': {}
        }

        for container_name, logs in self.__current_run_logs.items():
            run_entry['containers'][container_name] = logs.copy()
        self.__all_runs_logs.append(run_entry)

        # Clear current run logs now that they've been copied to cumulative
        self.__current_run_logs.clear()
        self.__phases.clear()
        self.__end_measurement = None
        self.__join_default_network = False
        self.__services_to_pause_phase.clear()
        self.__join_default_network = False
        self.__docker_params.clear()
        self.__working_folder = self._repo_folder
        self.__working_folder_rel = ''
        self.__image_sizes.clear()
        self.__volume_sizes.clear()
        self.__warnings.clear()
        self.__usage_scenario_variables_used_buffer.clear()
        self.__include_playwright_ipc_version = None

        print(TerminalColors.OKBLUE, '-Cleanup gracefully completed', TerminalColors.ENDC)


    def set_filename(self, filename):
        """Update filename for reusing ScenarioRunner with different files"""
        self._original_filename = filename

    def run(self):
        '''
            The run method is just a wrapper for the intended sequential flow of a GMT run.
            Mainly designed to call the methods individually for testing, but also
            if the flow ever needs to repeat certain blocks.

            The runner is to be thought of as a state machine.

            Methods thus will behave differently given the runner was instantiated with different arguments.

        '''
        try:
            self._run_id = None  # Reset run ID for new run
            self._start_measurement() # we start as early as possible to include initialization overhead
            self._clear_caches()
            self._check_system('start')
            self._initialize_folder(self._tmp_folder)
            self._checkout_repository()
            self._load_yml_file()
            self._initial_parse()
            self._register_machine_id()
            self._import_metric_providers()
            self._populate_image_names()
            self._prepare_docker()
            self._check_running_containers_before_start()
            self._remove_docker_images()
            self._download_dependencies()
            self._initialize_run() # have this as close to the start of measurement
            if self._debugger.active:
                self._debugger.pause('Initial load complete. Waiting to start metric providers')

            self._start_metric_providers(allow_other=True, allow_container=False)
            if self._debugger.active:
                self._debugger.pause('metric-providers (non-container) start complete. Waiting to start measurement')

            self._custom_sleep(self._measurement_pre_test_sleep)

            self._start_phase('[BASELINE]')
            self._custom_sleep(self._measurement_baseline_duration)
            self._end_phase('[BASELINE]')

            if self._debugger.active:
                self._debugger.pause('Measurements started. Waiting to start container build')

            self._start_phase('[INSTALLATION]')
            self._build_docker_images()
            self._end_phase('[INSTALLATION]')

            self._save_image_and_volume_sizes()

            if self._debugger.active:
                self._debugger.pause('Container build complete. Waiting to start container boot')

            self._start_phase('[BOOT]')
            self._setup_networks()
            self._setup_services()
            self._end_phase('[BOOT]')

            self._check_running_containers_after_boot_phase()
            self._check_process_returncodes()

            if self._debugger.active:
                self._debugger.pause('Container setup complete. Waiting to start container providers')

            self._add_containers_to_metric_providers()
            self._start_metric_providers(allow_container=True, allow_other=False)

            if self._debugger.active:
                self._debugger.pause('Container providers started. Waiting to collect dependency information')

            self._collect_container_dependencies()

            if self._debugger.active:
                self._debugger.pause('Dependency collection complete. Waiting to start idle phase')

            self._start_phase('[IDLE]')
            self._custom_sleep(self._measurement_idle_duration)
            self._end_phase('[IDLE]')

            if self._debugger.active:
                self._debugger.pause('Container idle phase complete. Waiting to start flows')

            self._start_phase('[RUNTIME]')
            self._run_flows() # can trigger debug breakpoints;
            self._end_phase('[RUNTIME]')

            self._check_running_containers_after_runtime_phase()

            if self._debugger.active:
                self._debugger.pause('Container flows complete. Waiting to start remove phase')

            self._start_phase('[REMOVE]')
            self._custom_sleep(1)
            self._end_phase('[REMOVE]')

            if self._debugger.active:
                self._debugger.pause('Remove phase complete. Waiting to stop and cleanup')

            self._end_measurement()
            self._check_process_returncodes()
            self._check_system('end')
            self._custom_sleep(self._measurement_post_test_sleep)
            self._identify_invalid_run()

        except BaseException as exc:
            self._add_to_current_run_log(
                container_name='[SYSTEM]',
                log_type=LogType.EXCEPTION,
                log_id=id(exc),
                cmd='run_scenario',
                phase='[RUNTIME]',
                stderr=f"{str(exc)}\n\n{exc.stderr}" if hasattr(exc, 'stderr') else str(exc),
                stdout=exc.stdout if hasattr(exc, 'stdout') else None,
                exception_class=exc.__class__.__name__
            )
            self._set_run_failed()
            raise exc
        finally:
            try:
                self._post_process(0)
            finally:
                self.cleanup()


        print(TerminalColors.OKGREEN, arrows('MEASUREMENT SUCCESSFULLY COMPLETED'), TerminalColors.ENDC)

        return self._run_id
