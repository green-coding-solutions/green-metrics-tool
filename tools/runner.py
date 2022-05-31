#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import subprocess
import json
import os
import signal
import time
import sys
import traceback
from import_stats import import_stats # local file import
from save_notes import save_notes # local file import
from lib.setup_functions import get_db_connection, get_config

# TODO:
# - Exception Logic is not really readable. Better encapsulate docker calls and fetch exception there
# - MAke function for arg reading and checking it's presence. More readable than el.get and exception and bottom
# - No cleanup is currently done if exception fails. System is in unclean state
# - No checks for possible command injections are done at the moment

def end_error(*errors):
    log_error(*errors)
    exit(2)

def log_error(*errors):
    print("Error: ", *errors)
    exception_type, exception_object, exception_traceback = sys.exc_info()
    filename = exception_traceback.tb_frame.f_code.co_filename
    line_number = exception_traceback.tb_lineno
    print("Exception type: ", exception_type)
    print("File name: ", filename)
    print("Line number: ", line_number)
    traceback.print_exc()
    # TODO: log to file

config = get_config()
conn = get_db_connection(config)

parser = argparse.ArgumentParser()
parser.add_argument("mode", help="Select the operation mode. Select `manual` to supply a directory or url on the command line. Or select `cron` to process database queue. For database mode the config.yml file will be read", choices=['manual', 'cron'])
parser.add_argument("--url", type=str, help="The url. Will only be read in manual mode")
parser.add_argument("--folder", type=str, help="The folder that contains your usage scenario as local path")

args = parser.parse_args() # script will exit if url is not present

if args.mode == 'manual' :
    if(args.folder is None and args.url is None):
        print('In manual mode please supply --folder as folder path or --url as URI\n')
        parser.print_help()
        exit(2)
    else:
        folder = args.folder
        url = args.url
        name = "manual-job"
        usage_scenario_file = folder +'/usage_scenario.json'

        cur = conn.cursor()
        cur.execute('INSERT INTO "projects" ("name","url","email","crawled","last_crawl","created_at") \
                    VALUES \
                    (%s,%s,\'manual\',FALSE,NULL,NOW()) RETURNING id;', (name,url))
        conn.commit()
        project_id = cur.fetchone()[0]

        cur.close()

elif args.mode == 'cron':

    cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM projects WHERE crawled = False ORDER BY created_at ASC LIMIT 1")
    data = cur.fetchone()
    if(data is None or data == []):
        print("No job to process. Exiting")
        exit(1)
    url = data['url']
    email = data['email']
    project_id = data['id']
    usage_scenario_file = '/tmp/repo/usage_scenario.json'
    cur.close()

    # set to crawled = 1, so we don't error loop
    cur = conn.cursor()
    cur.execute("UPDATE projects SET crawled = True WHERE id = %s", (project_id,))
    conn.commit()
    cur.close()



else:
    raise Exception('Unknown mode: ', args.mode)


containers = []
pids_to_kill = []

try:
    if url is not None :
        subprocess.run(["git", "clone", url, "/tmp/repo"], check=True, capture_output=True, encoding='UTF-8') # always name target-dir repo according to spec
    # TODO error handling

    with open(usage_scenario_file) as fp:
        obj = json.load(fp)

    print("Having Usage Scenario ", obj['name'])
    print("From: ", obj['author'])
    print("Version ", obj['version'], "\n")

    ps = subprocess.run(["uname", "-s"], check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, encoding='UTF-8')
    output = ps.stdout.strip().lower()

    if obj.get('architecture') is not None and output != obj['architecture']:
        end_error("Specified architecture does not match system architecture: system (%s) != specified (%s)", output, obj['architecture'])

    for el in obj['setup']:
        if el['type'] == 'container':
            containers.append(el['name'])
            container_name = el['name']

            print("Resetting container")
            subprocess.run(['docker', 'stop', container_name]) # often not running. so no check=true
            subprocess.run(['docker', 'rm', container_name]) # often not running. so no check=true

            print("Creating container")
            docker_run_string = ['docker', 'run', '-i', '-d', '--name', container_name, '-v', '/tmp/repo:/tmp/repo']

            if 'portmapping' in el:
                docker_run_string.append('-p')
                docker_run_string.append(el['portmapping'])

            docker_run_string.append(el['identifier'])

            ps = subprocess.run(
                docker_run_string,
                check=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                encoding="UTF-8"
            )
            print("Stdout:", ps.stdout)

            if "setup-commands" not in el.keys(): continue # setup commands are optional
            print("Running commands")
            for cmd in el['setup-commands']:
                print("Running command: docker exec -t", cmd)
                ps = subprocess.run(
                    ['docker', 'exec', container_name, *cmd.split()],
                    check=True,
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    encoding="UTF-8"
                )
                print("Stdout:", ps.stdout)
        else:
            end_error("Unknwown type detected in setup: ", el.get('type', None))

    # --- setup finished

    # start the measurement

    stats_process = subprocess.Popen(
        ["docker stats --no-trunc --format '{{.Name}};{{.CPUPerc}};{{.MemUsage}};{{.NetIO}}' " + ' '.join(containers) + "  > /tmp/docker_stats.log &"],
        shell=True,
        preexec_fn=os.setsid
    )
    pids_to_kill.append(stats_process.pid)

    notes = [] # notes may have duplicate timestamps, therefore list and no dict structure

    print("Pre-idling containers")
    time.sleep(5) # 5 seconds buffer at the start to idle container

    print("Current known containers: ", containers)

    # run the flows
    for el in obj['flow']:
        print("Running flow: ", el['name'])
        for inner_el in el['commands']:

            if inner_el['type'] == 'console':
                print("Console command", inner_el['command'], "on container", el['container'])

                docker_exec_command = ['docker', 'exec', '-t']


                if ("detach" in inner_el) and inner_el["detach"] == True :
                    print("Detaching")
                    docker_exec_command.append('-d')

                docker_exec_command.append(el['container'])
                docker_exec_command.extend( inner_el['command'].split(' ') )

                ps = subprocess.Popen(
                    " ".join(docker_exec_command),
                    shell=True,
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    encoding="UTF-8",
                    preexec_fn=os.setsid
                )

                if ("detach" in inner_el) and inner_el["detach"] == True :
                    pids_to_kill.append(ps.pid)

                print("Output of command ", inner_el['command'], "\n", ps.stdout.read())
            else:
                end_error('Unknown command type in flows: ', inner_el['type'])

            if "note" in inner_el: notes.append({"note" : inner_el['note'], 'container_name' : el['container'], "timestamp": time.time_ns()})

    print("Re-idling containers")
    time.sleep(5) # 5 seconds buffer at the end to idle container

    for pid in pids_to_kill:
        print("Killing: ", pid)
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass # process may have already ended

    print("Parsing stats")
    import_stats(conn, project_id, "/tmp/docker_stats.log")
    save_notes(conn, project_id, notes)

    if args.mode == 'manual':
        print(f"Please access your report with the ID: {project_id}")
    else:
        from send_report_email import send_report_email # local file import
        send_report_email(config, email, project_id)

except FileNotFoundError as e:
    log_error("Docker command failed.", e)
except subprocess.CalledProcessError as e:
    log_error("Docker command failed")
    log_error("Stdout:", e.stdout)
    log_error("Stderr:", e.stderr)
except KeyError as e:
    log_error("Was expecting a value inside the JSON file, but value was missing: ", e)
except BaseException as e:
    log_error("Base exception occured: ", e)
finally:
    for container_name in containers:
        subprocess.run(['docker', 'stop', container_name])  # often not running. so no check=true
        subprocess.run(['docker', 'rm', container_name])  # often not running. so no check=true

    for pid in pids_to_kill:
        print("Killing: ", pid)
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass # process may have already ended

    exit(2)



