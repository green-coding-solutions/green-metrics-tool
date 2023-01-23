#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Here we need to disable the import checking as pylint doesn't understand the witchcraft of changing sys.path
#pylint: disable=wrong-import-order,wrong-import-position,import-error

# We disable naming convention to allow names like p,kv etc. Even if it is not 'allowed' it makes the code more readable
#pylint: disable=invalid-name

# As pretty much everything is done in one big flow we trigger all the too-many-* checks. Which normally makes sense
# but in this case it would make the code a lot more complicated separating this out into loads of sub-functions
#pylint: disable=too-many-branches,too-many-statements,too-many-arguments,too-many-locals,too-many-instance-attributes

# Using a very broad exception makes sense in this case as we have excepted all the specific ones before
#pylint: disable=broad-except

# To make the code more readable we allow `project_id` in `main` and in method parameters to make clear that it is the
# same thing
#pylint: disable=redefined-outer-name

import subprocess
import json
import os
import time
import sys
import importlib
import yaml
import faulthandler
import re
from io import StringIO

faulthandler.enable()  # will catch segfaults and write to STDERR

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../lib")

from debug_helper import DebugHelper
from terminal_colors import TerminalColors
import process_helpers
import hardware_info
import error_helpers
from db import DB
from global_config import GlobalConfig
from save_notes import save_notes  # local file import

def arrows(text):
    return f"\n\n>>>> {text} <<<<\n\n"

class Runner:
    def __init__(self,
        debug_mode=False, allow_unsafe=False, no_file_cleanup=False, skip_unsafe=False, verbose_provider_boot=False):
        self.debug_mode = debug_mode
        self.allow_unsafe = allow_unsafe
        self.no_file_cleanup = no_file_cleanup
        self.skip_unsafe = skip_unsafe
        self.verbose_provider_boot = verbose_provider_boot

        self.containers = {}
        self.networks = []
        self.ps_to_kill = []
        self.ps_to_read = []
        self.metric_providers = []

    def run(self, uri, uri_type, project_id, filename='usage_scenario.yml', branch=None):

        config = GlobalConfig().config

        # Instantiate debug helper with correct mode
        debug = DebugHelper(self.debug_mode)

        subprocess.run(['rm', '-Rf', '/tmp/green-metrics-tool'], check=True, stderr=subprocess.DEVNULL)
        subprocess.run(['mkdir', '/tmp/green-metrics-tool'], check=True)

        if uri_type == 'URL':
            # always remove the folder if URL provided, cause -v directory binding always creates it
            # no check cause might fail when directory might be missing due to manual delete
            folder = '/tmp/green-metrics-tool/repo'
            if branch:
                print(f"Branch specified: {branch}")
                # git clone -b <branchname> --single-branch <remote-repo-url>
                subprocess.run(
                    [
                        'git',
                        'clone',
                        '--depth', '1',
                        '-b', branch,
                        '--single-branch',
                        '--recurse-submodules',
                        '--shallow-submodules',
                        uri,
                        '/tmp/green-metrics-tool/repo'
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
                        uri,
                        '/tmp/green-metrics-tool/repo'
                    ],
                    check=True,
                    capture_output=True,
                    encoding='UTF-8'
                )  # always name target-dir repo according to spec
        else:
            folder = uri

        with open(f"{folder}/{filename}", encoding='utf-8') as fp:
            obj = yaml.safe_load(fp)

        print(TerminalColors.HEADER, '\nHaving Usage Scenario ', obj['name'], TerminalColors.ENDC)
        print('From: ', obj['author'])
        print('Version ', obj['version'], '\n')

        if self.allow_unsafe:
            print(TerminalColors.WARNING, arrows('Warning: Runner is running in unsafe mode'), TerminalColors.ENDC)

        # Sanity checks first, before we insert anything in DB and rely on the linux subsystem to be present.
        # ATM only linux is working https://github.com/green-coding-berlin/green-metrics-tool/issues/96
        ps = subprocess.run(['uname', '-s'],
            check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, encoding='UTF-8')
        output = ps.stdout.strip().lower()

        if obj.get('architecture') is not None and output != obj['architecture']:
            raise RuntimeError('Specified architecture does not match system architecture:'
                f"system ({output}) != specified ({obj['architecture']})")

        # Insert auxilary info for the run. Not critical.
        DB().query("""UPDATE projects
            SET machine_specs=%s, measurement_config=%s, usage_scenario = %s, last_run = NOW()
            WHERE id = %s
            """, params=(
            json.dumps(hardware_info.get_values()),
            json.dumps(config['measurement']),
            json.dumps(obj),
            project_id)
        )

        # Import metric providers dynamically
        print(TerminalColors.HEADER, '\nImporting metric providers', TerminalColors.ENDC)
        # will iterate over keys
        for metric_provider in config['measurement']['metric-providers']:
            module_path, class_name = metric_provider.rsplit('.', 1)
            module_path = f"metric_providers.{module_path}"

            print(f"Importing {class_name} from {module_path}")
            print(f"Configuration is {config['measurement']['metric-providers'][metric_provider]}")
            module = importlib.import_module(module_path)
            # the additional () creates the instance
            metric_provider_obj = getattr(module, class_name)(
                resolution=config['measurement']['metric-providers'][metric_provider]['resolution'])

            self.metric_providers.append(metric_provider_obj)

        self.metric_providers.sort(key=lambda item: 'rapl' not in item.__class__.__name__.lower())

        if debug.active:
            debug.pause('Initial load complete. Waiting to start network setup')

        if 'networks' in obj:  # for some rare containers there is no network, like machine learning for example
            print(TerminalColors.HEADER, '\nSetting up networks', TerminalColors.ENDC)
            for network in obj['networks']:
                print('Creating network: ', network)
                # remove first if present to not get error, but do not make check=True, as this would lead to inf. loop
                subprocess.run(['docker', 'network', 'rm', network], stderr=subprocess.DEVNULL, check=False)
                subprocess.run(['docker', 'network', 'create', network], check=True)
                self.networks.append(network)

        if debug.active:
            debug.pause('Initial load complete. Waiting to start container setup')

        for container_name in obj['services']:
            print(TerminalColors.HEADER, '\nSetting up containers', TerminalColors.ENDC)

            service = obj['services'][container_name]

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
                docker_run_string.append(f"{folder}:{service['folder-destination']}:ro")
            else:
                docker_run_string.append(f"{folder}:/tmp/repo:ro")

            if 'volumes' in service:
                if self.allow_unsafe:
                    if not isinstance(service['volumes'], list):
                        raise RuntimeError(f"Volumes must be a list but is: {type(service['volumes'])}")
                    for volume in service['volumes']:
                        docker_run_string.append('-v')
                        docker_run_string.append(f"{volume}")
                elif self.skip_unsafe:
                    print(TerminalColors.WARNING,
                          arrows('Found volumes entry but not running in unsafe mode. Skipping'),
                          TerminalColors.ENDC)
                else:
                    raise RuntimeError('Found "volumes" but neither --skip-unsafe nor --allow-unsafe is set')

            if 'ports' in service:
                if self.allow_unsafe:
                    if not isinstance(service['ports'], list):
                        raise RuntimeError(f"ports must be a list but is: {type(service['ports'])}")
                    for ports in service['ports']:
                        print('Setting ports: ', service['ports'])
                        docker_run_string.append('-p')
                        docker_run_string.append(ports)
                elif self.skip_unsafe:
                    print(TerminalColors.WARNING,
                          arrows('Found ports entry but not running in unsafe mode. Skipping'),
                          TerminalColors.ENDC)
                else:
                    raise RuntimeError('Found "ports" but neither --skip-unsafe nor --allow-unsafe is set')

            if 'environment' in service:
                for docker_env_var in service['environment']:
                    if not self.allow_unsafe and re.search(r'^[A-Z_]+$', str(docker_env_var)) is None:
                        if self.skip_unsafe:
                            warn_message= arrows(f"Found environment var key with wrong format. \
                                 Only ^[A-Z_]+$ allowed: {docker_env_var} - Skipping")
                            print(TerminalColors.WARNING, warn_message, TerminalColors.ENDC)
                            continue
                        raise RuntimeError(f"Docker container setup environment var key had wrong format. \
                            Only ^[A-Z_]+$ allowed: {docker_env_var} - Maybe consider using --allow-unsafe \
                                or --skip-unsafe")

                    if not self.allow_unsafe and \
                        re.search(r'^[a-zA-Z_]+[a-zA-Z0-9_-]*$', str(service['environment'][docker_env_var])) is None:
                        if self.skip_unsafe:
                            print(TerminalColors.WARNING, arrows(f"Found environment var value with wrong format. \
                                    Only ^[A-Z_]+[a-zA-Z0-9_]*$ allowed: {service['environment'][docker_env_var]} - \
                                    Skipping"), TerminalColors.ENDC)
                            continue
                        raise RuntimeError(f"Docker container setup environment var value had wrong format. \
                            Only ^[A-Z_]+[a-zA-Z0-9_]*$ allowed: {service['environment'][docker_env_var]} - \
                            Maybe consider using --allow-unsafe --skip-unsafe")

                    docker_run_string.append('-e')
                    docker_run_string.append(f"{docker_env_var}={service['environment'][docker_env_var]}")

            if 'networks' in service:
                for network in service['networks']:
                    docker_run_string.append('--net')
                    docker_run_string.append(network)

            docker_run_string.append(service['image'])

            if 'cmd' in service:  # must come last
                docker_run_string.append(service['cmd'])

            print(f"Running docker run with: {docker_run_string}")

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
            self.containers[container_id] = container_name
            print('Stdout:', container_id)

            if 'setup-commands' not in service:
                continue  # setup commands are optional
            print('Running commands')
            for cmd in service['setup-commands']:
                print('Running command: docker exec ', cmd)

                # docker exec must stay as list, cause this forces items to be quoted and escaped and prevents
                # injection of unwawnted params
                ps = subprocess.run(
                    ['docker', 'exec', container_name, *cmd.split()],
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

        # --- setup finished

        print(TerminalColors.HEADER, '\nCurrent known containers: ', self.containers, TerminalColors.ENDC)

        if debug.active:
            debug.pause('Container setup complete. Waiting to start metric-providers')

        print(TerminalColors.HEADER, '\nStarting metric providers', TerminalColors.ENDC)

        notes = []  # notes may have duplicate timestamps, therefore list and no dict structure

        for metric_provider in self.metric_providers:
            message = f"Booting {metric_provider.__class__.__name__}"
            print(message)
            metric_provider.start_profiling(self.containers)
            if self.verbose_provider_boot:
                notes.append({'note': message, 'detail_name': '[SYSTEM]', 'timestamp': int(
                    time.time_ns() / 1_000)})
                time.sleep(2)

        print(TerminalColors.HEADER, '\nWaiting for Metric Providers to boot ...', TerminalColors.ENDC)
        time.sleep(2)

        for metric_provider in self.metric_providers:
            stderr_read = metric_provider.get_stderr()
            print(f"Stderr check on {metric_provider.__class__.__name__}")
            if stderr_read is not None:
                raise RuntimeError(f"Stderr on {metric_provider.__class__.__name__} was NOT empty: {stderr_read}")

        print(TerminalColors.HEADER,
              f"\nPre-idling containers for {config['measurement']['idle-time-start']}s", TerminalColors.ENDC)
        notes.append({'note': 'Pre-idling containers',
                     'detail_name': '[SYSTEM]', 'timestamp': int(time.time_ns() / 1_000)})

        time.sleep(config['measurement']['idle-time-start'])

        if debug.active:
            debug.pause('metric-providers start complete. Waiting to start flow')

        start_measurement = int(time.time_ns() / 1_000)
        notes.append({'note': 'Start of measurement',
                     'detail_name': '[SYSTEM]', 'timestamp': start_measurement})

        try:
            # run the flows
            for el in obj['flow']:
                print(TerminalColors.HEADER, '\nRunning flow: ', el['name'], TerminalColors.ENDC)
                for inner_el in el['commands']:
                    if 'note' in inner_el:
                        notes.append({'note': inner_el['note'], 'detail_name': el['container'], 'timestamp': int(
                            time.time_ns() / 1_000)})

                    if inner_el['type'] == 'console':
                        print(TerminalColors.HEADER, '\nConsole command',
                              inner_el['command'], 'on container', el['container'], TerminalColors.ENDC)

                        docker_exec_command = ['docker', 'exec']

                        docker_exec_command.append(el['container'])
                        docker_exec_command.extend(inner_el['command'].split(' '))

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

                        self.ps_to_read.append({
                            'cmd': docker_exec_command,
                            'ps': ps,
                            'read-notes-stdout': inner_el.get('read-notes-stdout', False),
                            'ignore-errors': inner_el.get('ignore-errors', False),
                            'detail_name': el['container']})

                        if inner_el.get('detach', None) is True:
                            print('Process should be detached. Running asynchronously and detaching ...')
                            self.ps_to_kill.append({'ps': ps, 'cmd': inner_el['command'], 'ps_group': False})
                        else:
                            print(f"Process should be synchronous. \
                                Alloting {config['measurement']['flow-process-runtime']}s runtime ...")
                            process_helpers.timeout(
                                ps, inner_el['command'], config['measurement']['flow-process-runtime'])
                    else:
                        raise RuntimeError('Unknown command type in flow: ', inner_el['type'])

                    if debug.active:
                        debug.pause('Waiting to start next command in flow')

            end_measurement = int(time.time_ns() / 1_000)
            notes.append({'note': 'End of measurement', 'detail_name': '[SYSTEM]', 'timestamp': end_measurement})

            print(TerminalColors.HEADER,
                  f"\nIdling containers after run for {config['measurement']['idle-time-end']}s", TerminalColors.ENDC)

            time.sleep(config['measurement']['idle-time-end'])

            notes.append({'note': 'End of post-measurement idle',
                'detail_name': '[SYSTEM]', 'timestamp': int(time.time_ns() / 1_000)})

            print(TerminalColors.HEADER, 'Stopping metric providers and parsing stats', TerminalColors.ENDC)
            for metric_provider in self.metric_providers:
                stderr_read = metric_provider.get_stderr()
                if stderr_read is not None:
                    raise RuntimeError(
                        f"Stderr on {metric_provider.__class__.__name__} was NOT empty: {stderr_read}")

                metric_provider.stop_profiling()

                df = metric_provider.read_metrics(project_id, self.containers)
                print('Imported', TerminalColors.HEADER,
                      df.shape[0], TerminalColors.ENDC, 'metrics from ', metric_provider.__class__.__name__)
                if df is None or df.shape[0] == 0:
                    raise RuntimeError(
                        f"No metrics were able to be imported from: {metric_provider.__class__.__name__}")

                f = StringIO(df.to_csv(index=False, header=False))
                DB().copy_from(file=f, table='stats', columns=df.columns, sep=',')

            # now we have free capacity to parse the stdout / stderr of the processes
            print(TerminalColors.HEADER, '\nGetting output from processes: ', TerminalColors.ENDC)
            for ps in self.ps_to_read:
                for line in process_helpers.parse_stream_generator(ps['ps'], ps['cmd'], ps['ignore-errors']):
                    print('Output from process: ', line)
                    if ps['read-notes-stdout']:
                        # Fixed format according to our specification. If unpacking fails this is wanted error
                        timestamp, note = line.split(' ', 1)
                        notes.append({'note': note, 'detail_name': ps['detail_name'], 'timestamp': timestamp})

            # kill process only after reading. Otherwise the stream buffer might be gone
            process_helpers.kill_ps(self.ps_to_kill)
        finally:
            # we here only want the header to be colored, not the notes itself
            print(TerminalColors.HEADER, '\nSaving notes: ', TerminalColors.ENDC, notes)
            save_notes(project_id, notes)

        print(TerminalColors.HEADER, '\nUpdating start and end measurement times', TerminalColors.ENDC)
        DB().query("""UPDATE projects
            SET start_measurement=%s, end_measurement=%s
            WHERE id = %s
            """, params=(start_measurement, end_measurement, project_id))

        self.cleanup()  # always run cleanup automatically after each run

        print(TerminalColors.OKGREEN, arrows('MEASUREMENT SUCCESSFULLY COMPLETED'), TerminalColors.ENDC)

    def cleanup(self):
        #https://github.com/green-coding-berlin/green-metrics-tool/issues/97
        print(TerminalColors.OKCYAN, '\nStarting cleanup routine', TerminalColors.ENDC)

        print('Stopping metric providers')
        for metric_provider in self.metric_providers:
            metric_provider.stop_profiling()

        print('Stopping containers')
        for container_name in self.containers.values():
            subprocess.run(['docker', 'rm', '-f', container_name], check=True, stderr=subprocess.DEVNULL)

        print('Removing network')
        for network_name in self.networks:
            # no check=True, as the network might already be gone. We do not want to fail here
            subprocess.run(['docker', 'network', 'rm', network_name], stderr=subprocess.DEVNULL, check=False)

        if not self.no_file_cleanup:
            print('Removing files')
            subprocess.run(['rm', '-Rf', '/tmp/green-metrics-tool'], stderr=subprocess.DEVNULL, check=True)

        process_helpers.kill_ps(self.ps_to_kill)
        print(TerminalColors.OKBLUE, '-Cleanup gracefully completed', TerminalColors.ENDC)

        self.containers = {}
        self.networks = []
        self.ps_to_kill = []
        self.ps_to_read = []
        self.metric_providers = []


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
        sys.exit(2)

    if args.allow_unsafe and args.skip_unsafe:
        parser.print_help()
        error_helpers.log_error('--allow-unsafe and skip--unsafe in conjuction is not possible')
        sys.exit(2)

    if args.name is None:
        parser.print_help()
        error_helpers.log_error('Please supply --name')
        sys.exit(2)

    if args.uri[0:8] == 'https://' or args.uri[0:7] == 'http://':
        print('Detected supplied URL: ', args.uri)
        run_type = 'URL'
    elif args.uri[0:1] == '/':
        print('Detected supplied folder: ', args.uri)
        run_type = 'folder'
        if not Path(args.uri).is_dir():
            parser.print_help()
            error_helpers.log_error('Could not find folder on local system. Please double check: ', args.uri)
            sys.exit(2)
    else:
        parser.print_help()
        error_helpers.log_error('Could not detected correct URI. \
            Please use local folder in Linux format /folder/subfolder/... or URL http(s):// : ', args.uri)
        sys.exit(2)

    # We issue a fetch_one() instead of a query() here, cause we want to get the project_id
    project_id = DB().fetch_one('INSERT INTO "projects" ("name","uri","email","last_run","created_at", "branch") \
                VALUES \
                (%s,%s,\'manual\',NULL,NOW(),%s) RETURNING id;', params=(args.name, args.uri, args.branch))[0]

    runner = Runner(debug_mode=args.debug, allow_unsafe=args.allow_unsafe, no_file_cleanup=args.no_file_cleanup,
                    skip_unsafe=args.skip_unsafe, verbose_provider_boot=args.verbose_provider_boot)
    try:
        runner.run(uri=args.uri, uri_type=run_type,
                   project_id=project_id, filename=args.filename, branch=args.branch)  # Start main code
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
    finally:
        runner.cleanup()  # run just in case. Will be noop on successful run
