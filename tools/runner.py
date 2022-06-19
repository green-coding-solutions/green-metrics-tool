#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import subprocess
import json
import os
import signal
import time
import traceback
import sys
import re

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../lib")

from import_stats import import_docker_stats, import_cgroup_stats, import_rapl # local file import
from save_notes import save_notes # local file import
from setup_functions import get_db_connection, get_config
from errors import log_error, end_error, email_error

# TODO:
# - Exception Logic is not really readable. Better encapsulate docker calls and fetch exception there
# - Make function for arg reading and checking it's presence. More readable than el.get and exception and bottom
# - No cleanup is currently done if exception fails. System is in unclean state
# - No checks for possible command injections are done at the moment

config = get_config()
conn = get_db_connection(config)

parser = argparse.ArgumentParser()
parser.add_argument("mode", help="Select the operation mode. Select `manual` to supply a directory or url on the command line. Or select `cron` to process database queue. For database mode the config.yml file will be read", choices=['manual', 'cron'])
parser.add_argument("--url", type=str, help="The url to download the repository with the usage_scenario.json from. Will only be read in manual mode.")
parser.add_argument("--name", type=str, help="A name which will be stored to the database to discern this run from others. Will only be read in manual mode.")
parser.add_argument("--folder", type=str, help="The folder that contains your usage scenario as local path. Will only be read in manual mode.")
parser.add_argument("--no-file-cleanup", type=str, help="Do not delete files in /tmp/green-metrics-tool")
parser.add_argument("--debug", type=str, help="Activate steppable debug mode")

args = parser.parse_args() # script will exit if url is not present

user_email,project_id=None

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

    cur = conn.cursor()
    cur.execute('INSERT INTO "projects" ("name","url","email","crawled","last_crawl","created_at") \
                VALUES \
                (%s,%s,\'manual\',TRUE,NOW(),NOW()) RETURNING id;', (name,url or folder))
    conn.commit()
    project_id = cur.fetchone()[0]

    cur.close()

elif args.mode == 'cron':

    cur = conn.cursor()
    cur.execute("SELECT id,url,email FROM projects WHERE crawled = False ORDER BY created_at ASC LIMIT 1")
    data = cur.fetchone()

    if(data is None or data == []):
        print("No job to process. Exiting")
        exit(1)

    project_id = data[0]
    url = data[1]
    email = data[2]
    user_email = email
    cur.close()

    # set to crawled = 1, so we don't error loop
    cur = conn.cursor()
    cur.execute("UPDATE projects SET crawled = True WHERE id = %s", (project_id,))
    conn.commit()
    cur.close()

else:
    raise Exception('Unknown mode: ', args.mode)

insert_hw_info(conn, project_id)

containers = {}
networks = []
pids_to_kill = []

try:

    subprocess.run(["rm", "-R", "/tmp/green-metrics-tool"])
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

    ps = subprocess.run(["uname", "-s"], check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, encoding='UTF-8')
    output = ps.stdout.strip().lower()

    if obj.get('architecture') is not None and output != obj['architecture']:
        raise Exception("Specified architecture does not match system architecture: system (%s) != specified (%s)", output, obj['architecture'])

    for el in obj['setup']:
        if el['type'] == 'container':
            container_name = el['name']

            print("Resetting container")
            subprocess.run(['docker', 'stop', container_name]) # often not running. so no check=true
            subprocess.run(['docker', 'rm', container_name]) # often not running. so no check=true

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

            if (args.debug is not None) and ('portmapping' in el):
                docker_run_string.append('-p')
                docker_run_string.append(el['portmapping'])

            if 'env' in el:
                import re
                for docker_env_var in el['env']:
                    if re.search("^[A-Z_]+$", docker_env_var) is None:
                        raise Exception(f"Docker container setup env var key had wrong format. Only ^[A-Z_]+$ allowed: {docker_env_var}")
                    if re.search("^[a-zA-Z_]+[a-zA-Z0-9_-]*$", el['env'][docker_env_var]) is None:
                        raise Exception(f"Docker container setup env var value had wrong format. Only ^[A-Z_]+[a-zA-Z0-9_]*$ allowed: {el['env'][docker_env_var]}")

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
            raise Exception("Unknown type detected in setup: ", el.get('type', None))

    # --- setup finished

    print("Current known containers: ", containers)

    # start the measurement

    print("Starting measurement provider docker stats")
    stats_process = subprocess.Popen(
        ["docker stats --no-trunc --format '{{.Name}};{{.CPUPerc}};{{.MemUsage}};{{.NetIO}}' " + ' '.join(containers.values()) + "  > /tmp/green-metrics-tool/docker_stats.log &"],
        shell=True,
        preexec_fn=os.setsid,
        encoding="UTF-8"
    )
    pids_to_kill.append(stats_process.pid)

    print("Starting measurement provider docker cgroup read")
    docker_cgroup_read_process = subprocess.Popen(
        [f"stdbuf -oL {current_dir}/docker-read 100 " + " ".join(containers.keys()) + " > /tmp/green-metrics-tool/docker_cgroup_read.log"],
        shell=True,
        preexec_fn=os.setsid
    )
    pids_to_kill.append(docker_cgroup_read_process.pid)


    # To issue this command as sudo it must be specifically allowed in the /etc/sudoers like so:
    # docker run  -d -p 8000:80 --net green-coding-net --name green-coding-nginx-gunicorn-container green-coding-nginx-gunicorn
    # arne	ALL=(ALL) NOPASSWD: PATH_TO/green-metrics-tool/tools/rapl-read
    print("Starting measurement provider RAPL read")
    rapl_process = subprocess.Popen(
        [f"sudo /usr/bin/stdbuf -oL {current_dir}/rapl-read -i 100 > /tmp/green-metrics-tool/rapl.log &"],
        shell=True,
        preexec_fn=os.setsid,
        encoding="UTF-8"
    )

    pids_to_kill.append(rapl_process.pid)


    notes = [] # notes may have duplicate timestamps, therefore list and no dict structure

    print("Pre-idling containers")

    time.sleep(5) # 5 seconds buffer at the start to idle container

    if args.debug is not None:
        print("Debug mode is active. Pausing. Please press any key to continue ...")
        sys.stdin.readline()

    notes.append({"note" : "[START MEASUREMENT]", 'container_name' : '[SYSTEM]', "timestamp": int(time.time_ns() / 1_000)})

    # run the flows
    for el in obj['flow']:
        print("Running flow: ", el['name'])
        for inner_el in el['commands']:

            if args.debug is not None:
                print("Debug mode is active. Pausing. Please press any key to continue ...")
                sys.stdin.readline()


            if "note" in inner_el:
                notes.append({"note" : inner_el['note'], 'container_name' : el['container'], "timestamp": int(time.time_ns() / 1_000)})

            if inner_el['type'] == 'console':
                print("Console command", inner_el['command'], "on container", el['container'])

                docker_exec_command = ['docker', 'exec']

                if inner_el.get('detach', None) == True :
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

                print(ps.stderr.readable())

                docker_exec_stderr = ps.stderr.read()
                if docker_exec_stderr != '':
                    raise Exception('Docker exec returned an error: ', docker_exec_stderr)

                if inner_el.get('detach', None) == True :
                    pids_to_kill.append(ps.pid)

                print("Output of command ", inner_el['command'], "\n", ps.stdout.read())
            else:
                raise Exception('Unknown command type in flows: ', inner_el['type'])

    notes.append({"note" : "[END MEASUREMENT]", 'container_name' : '[SYSTEM]', "timestamp": int(time.time_ns() / 1_000)})


    print("Re-idling containers")
    time.sleep(5) # 5 seconds buffer at the end to idle container

    for pid in pids_to_kill:
        print("Killing: ", pid)
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass # process may have already ended

    print("Parsing stats")

    #import_docker_stats(conn, project_id, "/tmp/green-metrics-tool/docker_stats.log")
    import_cgroup_stats(conn, project_id, containers, "/tmp/green-metrics-tool/docker_cgroup_read.log")
    import_rapl(conn, project_id, "/tmp/green-metrics-tool/rapl.log")

    save_notes(conn, project_id, notes)

    if args.mode == 'manual':
        print(f"Please access your report with the ID: {project_id}")
    else:
        from send_email import send_report_email # local file import
        send_report_email(config, email, project_id)

except FileNotFoundError as e:
    log_error("Docker command failed.", e)
    email_error("Docker command failed.", e, user_email=user_email, project_id=project_id)
except subprocess.CalledProcessError as e:
    log_error("Docker command failed")
    log_error("Stdout:", e.stdout)
    log_error("Stderr:", e.stderr)
    email_error("Docker command failed", "Stdout:", e.stdout, "Stderr:", e.stderr, user_email=user_email, project_id=project_id)
except KeyError as e:
    log_error("Was expecting a value inside the JSON file, but value was missing: ", e)
    email_error("Was expecting a value inside the JSON file, but value was missing: ", e, user_email=user_email, project_id=project_id)
except BaseException as e:
    log_error("Base exception occured: ", e)
    email_error("Base exception occured: ", e, user_email=user_email, project_id=project_id)
finally:
    for container_name in containers.values():
        subprocess.run(['docker', 'stop', container_name])
        subprocess.run(['docker', 'rm', container_name])

    for network_name in networks:
        subprocess.run(['docker', 'network', 'rm', network_name])

    if args.no_file_cleanup is None:
        subprocess.run(["rm", "-R", "/tmp/green-metrics-tool"])

    for pid in pids_to_kill:
        print("Killing: ", pid)
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass # process may have already ended

    exit(2)


def insert_hw_info(conn, project_id):
    with open("/proc/cpuinfo", "r")  as f:
        info = f.readlines()
    
    cpuinfo = [x.strip().split(": ")[1] for x in info if "model name"  in x]
    #print(cpuinfo[0])

    with open("/proc/meminfo", "r") as f:
        lines = f.readlines()
    memtotal = re.search(r"\d+", lines[0].strip())
    #print(memtotal.group())

    #lshw_output = subprocess.check_output(["lshw", "-C", "display"])
    #gpuinfo = re.search(r"product: (.*)$", lshw_output.decode("UTF-8"))
    #print(gpuinfo.group())

    cur = conn.cursor()
    cur.execute("""UPDATE projects 
        SET cpu=%s, memtotal=%s
        WHERE id = %s
        """, (cpuinfo[0], memtotal.group(), project_id))
    conn.commit()
    cur.close()


if __name__ == "__main__":
    print('hello')