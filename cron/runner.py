#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import subprocess
import json
import os
import signal
from parse_stats import import_stats # local import
import time

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
    # log to file


import yaml # conditional import. therefore here
with open("{path}/../config.yml".format(path=os.path.dirname(os.path.realpath(__file__)))) as config_file:
    config = yaml.load(config_file,yaml.FullLoader)
import psycopg2 # conditional import. therefore here
import psycopg2.extras
conn = psycopg2.connect("host=%s user=%s dbname=%s password=%s" % (config['postgresql']['host'], config['postgresql']['user'], config['postgresql']['dbname'], config['postgresql']['password']))


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
kill_stats_process = False

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
            ps = subprocess.run(
                ['docker', 'run', '-i', '-d', '--name', container_name, '-d', '-p', el['portmapping'], '-v', '/tmp/repo:/tmp/repo', el['identifier']],
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

    # setup the measurement


    kill_stats_process = True
    stats_process = subprocess.Popen(
        ["docker stats --no-trunc --format '{{.Name}};{{.CPUPerc}};{{.MemUsage}};{{.NetIO}}' > /tmp/docker_stats.log &"],
        shell=True,
        preexec_fn=os.setsid
    )

    print("Pre-idling containers")
    time.sleep(5) # 5 seconds buffer at the start to idle container

    print("Current known containers: ", containers)

    # run the flows
    for el in obj['flow']:
        print("Running flow: ", el['name'])
        for inner_el in el['commands']:

            if inner_el['type'] == 'console':
                print("Console command", inner_el['command'], "on container", el['container'])
                ps = subprocess.run(
                    ['docker', 'exec', '-t', el['container'], *(inner_el['command'].split(' ')) ],
                    check=True,
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    encoding="UTF-8"
                )
                print("Output of command ", inner_el['command'], "\n", ps.stdout.strip())

            else:
                end_error('Unknown command type in flows: ', inner_el['type'])

    print("Re-idling containers")
    time.sleep(5) # 5 seconds buffer at the end to idle container

    print("Parsing stats")
    import_stats(project_id, "/tmp/docker_stats.log", containers=containers)

    from send_email import send_report_email
    send_report_email(email, project_id)

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
    if(kill_stats_process): os.killpg(os.getpgid(stats_process.pid), signal.SIGTERM) # always kill the stats process. May fail though
    exit(2)



