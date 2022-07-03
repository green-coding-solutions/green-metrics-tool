#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import subprocess
import json
import os
import signal
import time
import sys
import re
import importlib

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../lib")
sys.path.append(f"{current_dir}/metric-providers")

from save_notes import save_notes # local file import
from setup_functions import get_config
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

def main():
    config = get_config()

    parser = argparse.ArgumentParser()
    parser.add_argument("mode", help="Select the operation mode. Select `manual` to supply a directory or url on the command line. Or select `cron` to process database queue. For database mode the config.yml file will be read", choices=['manual', 'cron'])
    parser.add_argument("--url", type=str, help="The url to download the repository with the usage_scenario.json from. Will only be read in manual mode.")
    parser.add_argument("--name", type=str, help="A name which will be stored to the database to discern this run from others. Will only be read in manual mode.")
    parser.add_argument("--folder", type=str, help="The folder that contains your usage scenario as local path. Will only be read in manual mode.")
    parser.add_argument("--no-file-cleanup", action='store_true', help="Do not delete files in /tmp/green-metrics-tool")
    parser.add_argument("--debug", action='store_true', help="Activate steppable debug mode")
    parser.add_argument("--unsafe", action='store_true', help="Activate unsafe volume bindings, portmappings and complex env vars")

    args = parser.parse_args() # script will exit if url is not present


    debug = DebugHelper(args.debug)

    user_email,project_id=None,None

    if(args.folder is not None and args.url is not None):
            print('Please supply only either --folder or --url\n')
            parser.print_help()
            exit(2)

    if args.mode == 'manual' :
        if(args.folder is None and args.url is None):
            print('In manual mode please supply --folder as folder path or --url as URI\n')
            parser.print_help()
            exit(2)

        if(args.name is None):
            print('In manual mode please supply --name\n')
            parser.print_help()
            exit(2)

        folder = args.folder
        url = args.url
        name = args.name

        project_id = DB().fetch_one('INSERT INTO "projects" ("name","url","email","crawled","last_crawl","created_at") \
                    VALUES \
                    (%s,%s,\'manual\',TRUE,NOW(),NOW()) RETURNING id;', params=(name,url or folder))[0]

    elif args.mode == 'cron':

        data = DB().fetch_one("SELECT id,url,email FROM projects WHERE crawled = False ORDER BY created_at ASC LIMIT 1")

        if(data is None or data == []):
            print("No job to process. Exiting")
            exit(1)

        project_id = data[0]
        url = data[1]
        email = data[2]
        user_email = email

        # set to crawled = 1, so we don't error loop
        DB().query("UPDATE projects SET crawled = True WHERE id = %s", params=(project_id,))

    else:
        raise RuntimeError('Unknown mode: ', args.mode)


    containers = {}
    networks = []
    ps_to_kill = []
    ps_to_read = []
    metric_providers = []

    try:

        subprocess.run(["rm", "-Rf", "/tmp/green-metrics-tool"])
        subprocess.run(["mkdir", "/tmp/green-metrics-tool"])

        if url is not None :
            # always remove the folder if URL provided, cause -v directory binding always creates it
            # no check cause might fail when directory might be missing due to manual delete
            subprocess.run(["git", "clone", url, "/tmp/green-metrics-tool/repo"], check=True, capture_output=True, encoding='UTF-8') # always name target-dir repo according to spec
            folder = '/tmp/green-metrics-tool/repo'

        with open(f"{folder}/usage_scenario.json") as fp:
            obj = json.load(fp)


        print("Having Usage Scenario ", obj['name'])
        print("From: ", obj['author'])
        print("Version ", obj['version'], "\n")

        hardware_info.insert_hw_info(project_id)
        DB().query('UPDATE "projects"  SET usage_scenario = %s WHERE id = %s ', (json.dumps(obj),project_id))

        for metric_provider in config['metric-providers']:
            print(f"Importing metric provider: {metric_provider}")
            metric_providers.append(importlib.import_module(metric_provider))


        ps = subprocess.run(["uname", "-s"], check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, encoding='UTF-8')
        output = ps.stdout.strip().lower()

        if obj.get('architecture') is not None and output != obj['architecture']:
            raise RuntimeError("Specified architecture does not match system architecture: system (%s) != specified (%s)", output, obj['architecture'])

        for el in obj['setup']:
            if el['type'] == 'container':
                container_name = el['name']

                print("Resetting container")
                subprocess.run(["docker", "rm", "-f", container_name])  # often not running. so no check=true

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

                if args.unsafe is True and 'volumes' in el:
                    if(type(el['volumes']) != list):
                        raise RuntimeError(f"Volumes must be a list but is: {type(el['volumes'])}")
                    for volume in el['volumes']:
                        docker_run_string.append('-v')
                        docker_run_string.append(f"{volume}:ro")

                if args.unsafe is True and 'portmapping' in el:
                    if(type(el['portmapping']) != list):
                        raise RuntimeError(f"Portmapping must be a list but is: {type(el['portmapping'])}")
                    for portmapping in el['portmapping']:
                        print("Setting portmapping: ", el['portmapping'])
                        docker_run_string.append('-p')
                        docker_run_string.append(portmapping)

                if 'env' in el:
                    import re
                    for docker_env_var in el['env']:
                        if args.unsafe is True and re.search("^[A-Z_]+$", docker_env_var) is None:
                            raise RuntimeError(f"Docker container setup env var key had wrong format. Only ^[A-Z_]+$ allowed: {docker_env_var}")
                        if args.unsafe is True and re.search("^[a-zA-Z_]+[a-zA-Z0-9_-]*$", el['env'][docker_env_var]) is None:
                            raise RuntimeError(f"Docker container setup env var value had wrong format. Only ^[A-Z_]+[a-zA-Z0-9_]*$ allowed: {el['env'][docker_env_var]}")

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
                containers[container_id] = container_name
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
                networks.append(el['name'])
            elif el['type'] == 'Dockerfile':
                raise NotImplementedError("Green Metrics Tool can currently not consume Dockerfiles. This will be a premium feature, as it creates a lot of server usage and thus slows down Tests per Minute for our server.")
            elif el['type'] == 'Docker-Compose':
                raise NotImplementedError("Green Metrics Tool will not support that, because we wont support all features from docker compose, like for instance volumes and binding arbitrary directories")
            else:
                raise RuntimeError("Unknown type detected in setup: ", el.get('type', None))

        # --- setup finished

        print("Current known containers: ", containers)

        for metric_provider in metric_providers:
            print(f"Starting measurement provider {metric_provider}")
            ps_to_kill.append({"pid": metric_provider.read(100, containers), "cmd": metric_provider, "ps_group": True})




        notes = [] # notes may have duplicate timestamps, therefore list and no dict structure

        print(f"Pre-idling containers for {config['measurement']['idle-time-start']}s")

        time.sleep(config['measurement']['idle-time-start'])

        debug.pause()

        notes.append({"note" : "[START MEASUREMENT]", 'container_name' : '[SYSTEM]', "timestamp": int(time.time_ns() / 1_000)})

        # run the flows
        for el in obj['flow']:
            print("Running flow: ", el['name'])
            for inner_el in el['commands']:

                debug.pause()

                if "note" in inner_el:
                    notes.append({"note" : inner_el['note'], 'container_name' : el['container'], "timestamp": int(time.time_ns() / 1_000)})

                if inner_el['type'] == 'console':
                    print("Console command", inner_el['command'], "on container", el['container'])

                    docker_exec_command = ['docker', 'exec']

                    docker_exec_command.append(el['container'])
                    docker_exec_command.extend( inner_el['command'].split(' ') )

                    # Note: In case of a detach wish in the usage_scenario.json:
                    # We are NOT using the -d flag from docker exec, as this prohibits getting the stdout.
                    # Since Popen always make the process asynchronous we can leverage this to emulate a detached behaviour
                    ps = subprocess.Popen(
                        docker_exec_command,
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        encoding="UTF-8"
                    )

                    ps_to_read.append({'cmd': docker_exec_command, 'ps': ps, 'read-notes-stdout': inner_el.get('read-notes-stdout', False), 'container_name': el['container']})

                    if inner_el.get('detach', None) == True :
                        print("Process should be detached. Running asynchronously and detaching ...")
                        ps_to_kill.append({"pid": ps.pid, "cmd": inner_el['command'], "ps_group": False})
                    else:
                        print(f"Process should be synchronous. Alloting {config['measurement']['flow-process-runtime']}s runtime ...")
                        process_helpers.timeout(ps, inner_el['command'], config['measurement']['flow-process-runtime'])
                else:
                    raise RuntimeError("Unknown command type in flow: ", inner_el['type'])

        notes.append({"note" : "[END MEASUREMENT]", 'container_name' : '[SYSTEM]', "timestamp": int(time.time_ns() / 1_000)})

        print(f"Idling containers after run for {config['measurement']['idle-time-end']}s")
        time.sleep(config['measurement']['idle-time-end'])

        # now we have free capacity to parse the stdout / stderr of the processes
        print("Getting output from processes: ")
        for ps in ps_to_read:
            for line in process_helpers.parse_stream_generator(ps['ps'], ps['cmd']):
                print("Output from process: ", line)
                if(ps['read-notes-stdout']):
                    timestamp, note = line.split(' ', 1) # Fixed format according to defintion. If unpacking fails this is wanted error
                    notes.append({"note" : note, 'container_name' : ps['container_name'], "timestamp": timestamp})



        process_helpers.kill_pids(ps_to_kill)

        print("Parsing stats")
        for metric_reporter in metric_providers:
            metric_reporter.import_stats(project_id, containers)


        print("Saving notes: ", notes)
        save_notes(project_id, notes)

        if args.mode == 'manual':
            print(f"Please access your report with the ID: {project_id}")
        else:
            from send_email import send_report_email # local file import
            send_report_email(config, email, project_id)

    except FileNotFoundError as e:
        error_helpers.email_and_log_error("Docker command failed.", e, user_email=user_email, project_id=project_id)
    except subprocess.CalledProcessError as e:
        error_helpers.email_and_log_error("Docker command failed", "Stdout:", e.stdout, "Stderr:", e.stderr, user_email=user_email, project_id=project_id)
    except KeyError as e:
        error_helpers.email_and_log_error("Was expecting a value inside the JSON file, but value was missing: ", e, user_email=user_email, project_id=project_id)
    except BaseException as e:
        error_helpers.email_and_log_error("Base exception occured: ", e, user_email=user_email, project_id=project_id)
    finally:
        print("Finally block. Stopping containers")
        for container_name in containers.values():
            subprocess.run(["docker", "rm", "-f", container_name])

        print("Removing network")
        for network_name in networks:
            subprocess.run(['docker', 'network', 'rm', network_name])

        if args.no_file_cleanup is None:
            print("Removing files")
            subprocess.run(["rm", "-Rf", "/tmp/green-metrics-tool"])

        process_helpers.kill_pids(ps_to_kill)
        print("\n\n>>> Shutdown gracefully completed <<<\n\n")

if __name__ == "__main__":
    main()
