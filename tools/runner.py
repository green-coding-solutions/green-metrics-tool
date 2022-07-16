#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import json
import os
import signal
import time
import sys
import re
import importlib
import yaml
from io import StringIO

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../lib")

from save_notes import save_notes # local file import
from global_config import GlobalConfig
from db import DB
import error_helpers
import hardware_info
import process_helpers

from debug_helper import DebugHelper

# TODO:
# - Exception Logic is not really readable. Better encapsulate docker calls and fetch exception there
# - Make function for arg reading and checking it's presence. More readable than el.get and exception and bottom
# - No cleanup is currently done if exception fails. System is in unclean state
# - No checks for possible command injections are done at the moment

class Runner:
    def __init__(self, debug_mode=False, unsafe_mode=False, no_file_cleanup=False):
        self.debug_mode = debug_mode
        self.unsafe_mode = unsafe_mode
        self.no_file_cleanup = no_file_cleanup

        self.containers = {}
        self.networks = []
        self.ps_to_kill = []
        self.ps_to_read = []
        self.metric_providers = []

    def run(self, uri, uri_type, project_id):

        config = GlobalConfig().config

        debug = DebugHelper(self.debug_mode) # Instantiate debug helper with correct mode


        subprocess.run(["rm", "-Rf", "/tmp/green-metrics-tool"])
        subprocess.run(["mkdir", "/tmp/green-metrics-tool"])

        if uri_type == 'URL' :
            # always remove the folder if URL provided, cause -v directory binding always creates it
            # no check cause might fail when directory might be missing due to manual delete
            subprocess.run(["git", "clone", uri, "/tmp/green-metrics-tool/repo"], check=True, capture_output=True, encoding='UTF-8') # always name target-dir repo according to spec
            folder = '/tmp/green-metrics-tool/repo'
        else:
            folder = uri

        with open(f"{folder}/usage_scenario.yml") as fp:
            obj = yaml.safe_load(fp)


        print("Having Usage Scenario ", obj['name'])
        print("From: ", obj['author'])
        print("Version ", obj['version'], "\n")

        if(self.unsafe_mode):
            print("\n\n>>>> Warning: Runner is running in unsafe mode <<<<<<\n\n")

        # Sanity checks first, before we insert anything in DB and rely on the linux subsystem to be present. ATM only linux is working
        # TODO: Refactor hardware calls later to be able to switch architectures
        ps = subprocess.run(["uname", "-s"], check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, encoding='UTF-8')
        output = ps.stdout.strip().lower()

        if obj.get('architecture') is not None and output != obj['architecture']:
            raise RuntimeError("Specified architecture does not match system architecture: system (%s) != specified (%s)", output, obj['architecture'])

        # Insert auxilary info for the run. Not critical.
        DB().query("""UPDATE projects
            SET machine_specs=%s, measurement_config=%s, usage_scenario = %s, last_run = NOW()
            WHERE id = %s
            """, params=(
                json.dumps({'cpu': hardware_info.get_cpu(), 'mem_total': hardware_info.get_mem()}),
                json.dumps(config['measurement']),
                json.dumps(obj),
                project_id)
            )

        # Import metric providers dynamically
        for metric_provider in config['measurement']['metric-providers']: # will iterate over keys
            module_path, class_name = metric_provider.rsplit('.', 1)
            module_path = f"metric_providers.{module_path}"

            print(f"Importing {class_name} from {module_path}")
            print(f"Resolution is {config['measurement']['metric-providers'][metric_provider]}")
            module = importlib.import_module(module_path)
            metric_provider_obj = getattr(module, class_name)(resolution=config['measurement']['metric-providers'][metric_provider]) # the additional () creates the instance

            self.metric_providers.append(metric_provider_obj)

        for el in obj['setup']:
            if el['type'] == 'container':
                container_name = el['name']

                print("Resetting container")
                subprocess.run(["docker", "rm", "-f", container_name], stderr=subprocess.DEVNULL)  # often not running. so no check=true

                print("Creating container")
                # We are attaching the -it option here to keep STDIN open and a terminal attached.
                # This helps to keep an excecutable-only container open, which would otherwise exit
                # This MAY break in the future, as some docker CLI implementation do not allow this and require
                # the command args to be passed on run only

                docker_run_string = ['docker', 'run', '-it', '-d', '--name', container_name]

                docker_run_string.append('-v')
                if 'folder-destination' in el:
                    docker_run_string.append(f"{folder}:{el['folder-destination']}:ro")
                else:
                    docker_run_string.append(f"{folder}:/tmp/repo:ro")

                if 'volumes' in el:
                    if self.unsafe_mode:
                        if(type(el['volumes']) != list):
                            raise RuntimeError(f"Volumes must be a list but is: {type(el['volumes'])}")
                        for volume in el['volumes']:
                            docker_run_string.append('-v')
                            docker_run_string.append(f"{volume}:ro")
                    else:
                        print('\n\n>>>>>>> Found volumes entry but not running in unsafe mode. Skipping <<<<<<<<\n\n', file=sys.stderr)

                if 'portmapping' in el:
                    if self.unsafe_mode:
                        if(type(el['portmapping']) != list):
                            raise RuntimeError(f"Portmapping must be a list but is: {type(el['portmapping'])}")
                        for portmapping in el['portmapping']:
                            print("Setting portmapping: ", el['portmapping'])
                            docker_run_string.append('-p')
                            docker_run_string.append(portmapping)
                    else:
                        print('\n\n>>>>>>> Found portmapping entry but not running in unsafe mode. Skipping <<<<<<<<\n\n', file=sys.stderr)

                if 'env' in el:
                    import re
                    for docker_env_var in el['env']:
                        if re.search("^[A-Z_]+$", docker_env_var) is None:
                            if not self.unsafe_mode:
                                 raise RuntimeError(f"Docker container setup env var key had wrong format. Only ^[A-Z_]+$ allowed: {docker_env_var} - Maybe consider using --unsafe")
                        if re.search("^[a-zA-Z_]+[a-zA-Z0-9_-]*$", el['env'][docker_env_var]) is None:
                            if not self.unsafe_mode:
                                 raise RuntimeError(f"Docker container setup env var value had wrong format. Only ^[A-Z_]+[a-zA-Z0-9_]*$ allowed: {el['env'][docker_env_var]} - Maybe consider using --unsafe")

                        docker_run_string.append('-e')
                        docker_run_string.append(f"{docker_env_var}={el['env'][docker_env_var]}")

                if 'network' in el:
                    docker_run_string.append('--net')
                    docker_run_string.append(el['network'])

                docker_run_string.append(el['identifier'])

                print(f"Running docker run with: {docker_run_string}")

                ps = subprocess.run(
                    docker_run_string,
                    check=True,
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    encoding="UTF-8"
                )

                container_id = ps.stdout.strip()
                self.containers[container_id] = container_name
                print("Stdout:", container_id)

                if "setup-commands" not in el.keys(): continue # setup commands are optional
                print("Running commands")
                for cmd in el['setup-commands']:
                    print("Running command: docker exec ", cmd)
                    ps = subprocess.run(
                        ["docker", "exec", container_name, *cmd.split()],
                        check=True,
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        encoding="UTF-8"
                    )
                    print("Stdout:", ps.stdout)
            elif el['type'] == 'network':
                print("Creating network: ", el['name'])
                subprocess.run(['docker', 'network', 'rm', el['name']]) # remove first if present to not get error
                subprocess.run(['docker', 'network', 'create', el['name']])
                self.networks.append(el['name'])
            elif el['type'] == 'Dockerfile':
                raise NotImplementedError("Green Metrics Tool can currently not consume Dockerfiles. This will be a premium feature, as it creates a lot of server usage and thus slows down Tests per Minute for our server.")
            elif el['type'] == 'Docker-Compose':
                raise NotImplementedError("Green Metrics Tool will not support that, because we wont support all features from docker compose, like for instance volumes and binding arbitrary directories")
            else:
                raise RuntimeError("Unknown type detected in setup: ", el.get('type', None))

        # --- setup finished

        print("Current known containers: ", self.containers)

        for metric_provider in self.metric_providers:
            print(f"Starting measurement provider {metric_provider.__class__.__name__}")
            metric_provider.start_profiling(self.containers)

        notes = [] # notes may have duplicate timestamps, therefore list and no dict structure

        print(f"Pre-idling containers for {config['measurement']['idle-time-start']}s")

        time.sleep(config['measurement']['idle-time-start'])

        debug.pause() # Will only pause if object state is currently "active"

        start_measurement = int(time.time_ns() / 1_000)

        # run the flows
        for el in obj['flow']:
            print("Running flow: ", el['name'])
            for inner_el in el['commands']:

                debug.pause() # Will only pause if object state is currently "active"

                if "note" in inner_el:
                    notes.append({"note" : inner_el['note'], 'container_name' : el['container'], "timestamp": int(time.time_ns() / 1_000)})

                if inner_el['type'] == 'console':
                    print("Console command", inner_el['command'], "on container", el['container'])

                    docker_exec_command = ['docker', 'exec']

                    docker_exec_command.append(el['container'])
                    docker_exec_command.extend( inner_el['command'].split(' ') )

                    # Note: In case of a detach wish in the usage_scenario.yml:
                    # We are NOT using the -d flag from docker exec, as this prohibits getting the stdout.
                    # Since Popen always make the process asynchronous we can leverage this to emulate a detached behaviour
                    ps = subprocess.Popen(
                        docker_exec_command,
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        encoding="UTF-8"
                    )

                    self.ps_to_read.append({'cmd': docker_exec_command, 'ps': ps, 'read-notes-stdout': inner_el.get('read-notes-stdout', False), 'container_name': el['container']})

                    if inner_el.get('detach', None) == True :
                        print("Process should be detached. Running asynchronously and detaching ...")
                        self.ps_to_kill.append({"pid": ps.pid, "cmd": inner_el['command'], "ps_group": False})
                    else:
                        print(f"Process should be synchronous. Alloting {config['measurement']['flow-process-runtime']}s runtime ...")
                        process_helpers.timeout(ps, inner_el['command'], config['measurement']['flow-process-runtime'])
                else:
                    raise RuntimeError("Unknown command type in flow: ", inner_el['type'])

        end_measurement = int(time.time_ns() / 1_000)

        print(f"Idling containers after run for {config['measurement']['idle-time-end']}s")
        time.sleep(config['measurement']['idle-time-end'])

        print("Stopping metric providers and parsing stats")
        for metric_provider in self.metric_providers:
            metric_provider.stop_profiling()

            df = metric_provider.read_metrics(project_id, self.containers)
            print(f"Imported {df.shape[0]} metrics from {metric_provider.__class__.__name__}")
            if df is None or df.shape[0] == 0:
                raise RuntimeError(f"No metrics were able to be imported from: {metric_provider.__class__.__name__}")

            f = StringIO(df.to_csv(index=False, header=False))
            DB().copy_from(file=f, table='stats', columns=df.columns, sep=",")


        # now we have free capacity to parse the stdout / stderr of the processes
        print("Getting output from processes: ")
        for ps in self.ps_to_read:
            for line in process_helpers.parse_stream_generator(ps['ps'], ps['cmd']):
                print("Output from process: ", line)
                if(ps['read-notes-stdout']):
                    timestamp, note = line.split(' ', 1) # Fixed format according to defintion. If unpacking fails this is wanted error
                    notes.append({"note" : note, 'container_name' : ps['container_name'], "timestamp": timestamp})

        process_helpers.kill_ps(self.ps_to_kill) # kill process only after reading. Otherwise the stream buffer might be gone

        print("Saving notes: ", notes)
        save_notes(project_id, notes)

        print("Updating start and end measurement times")
        DB().query("""UPDATE projects
            SET start_measurement=%s, end_measurement=%s
            WHERE id = %s
            """, params=(start_measurement, end_measurement, project_id))

        self.cleanup() # always run cleanup automatically after each run


    def cleanup(self): # TODO: Could be done when destroying object. but do we have all infos then?
        print("Finally block. Stopping containers")
        for container_name in self.containers.values():
            subprocess.run(["docker", "rm", "-f", container_name], stderr=subprocess.DEVNULL)

        print("Removing network")
        for network_name in self.networks:
            subprocess.run(['docker', 'network', 'rm', network_name], stderr=subprocess.DEVNULL)

        if self.no_file_cleanup is None:
            print("Removing files")
            subprocess.run(["rm", "-Rf", "/tmp/green-metrics-tool"])

        process_helpers.kill_ps(self.ps_to_kill)
        print("\n\n>>> Cleanup gracefully completed <<<\n\n")

        self.containers = {}
        self.networks = []
        self.ps_to_kill = []
        self.ps_to_read = []
        self.metric_providers = []

if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", type=str, help="The URI to get the usage_scenario.yml from. Can be eitehr file://... for local directories or http(s):// to download the repository with the usage_scenario.yml from.")
    parser.add_argument("--name", type=str, help="A name which will be stored to the database to discern this run from others. Will only be read in manual mode.")
    parser.add_argument("--no-file-cleanup", action='store_true', help="Do not delete files in /tmp/green-metrics-tool")
    parser.add_argument("--debug", action='store_true', help="Activate steppable debug mode")
    parser.add_argument("--unsafe", action='store_true', help="Activate unsafe volume bindings, portmappings and complex env vars")
    args = parser.parse_args()

    if args.uri is None:
        print('In manual mode please supply --uri\n')
        parser.print_help()
        exit(2)

    if args.uri[0:8] == 'https://' or args.uri[0:7] == 'http://':
        print("Detected supplied URL: ", args.uri)
        uri_type = 'URL'
    elif args.uri[0:1] == '/':
        print("Detected supplied folder: ", args.uri)
        uri_type = 'folder'
        if not Path(args.uri).is_dir():
            print("Could not find folder on local system. Please double check: ", args.uri, "\n")
            parser.print_help()
            exit(2)
    else:
        print("Could not detected correct URI. Please use local folder in Linux format /folder/subfolder/... or URL http(s):// : ", args.uri,  "\n")
        parser.print_help()
        exit(2)

    if args.name is None:
        print("In manual mode please supply --name\n")
        parser.print_help()
        exit(2)


    # We issue a fetch_one() instead of a query() here, cause we want to get the project_id
    project_id = DB().fetch_one('INSERT INTO "projects" ("name","uri","email","last_run","created_at") \
                VALUES \
                (%s,%s,\'manual\',NULL,NOW()) RETURNING id;', params=(args.name, args.uri))[0]

    runner = Runner(debug_mode=args.debug, unsafe_mode=args.unsafe, no_file_cleanup=args.no_file_cleanup)
    try:
        runner.run(uri=args.uri, uri_type=uri_type, project_id=project_id) # Start main code
        print(f"Please access your report with the ID: {project_id}")
    except FileNotFoundError as e:
        error_helpers.log_error("Docker command failed.", e, project_id)
    except subprocess.CalledProcessError as e:
        error_helpers.log_error("Docker command failed", "Stdout:", e.stdout, "Stderr:", e.stderr, project_id)
    except KeyError as e:
        error_helpers.log_error("Was expecting a value inside the JSON file, but value was missing: ", e, project_id)
    except BaseException as e:
        error_helpers.log_error("Base exception occured in runner.py: ", e, project_id)
    finally:
        runner.cleanup() # run just in case. Will be noop on successful run
