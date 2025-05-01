#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from lib.venv_checker import check_venv
check_venv() # this check must even run before __main__ as imports might not get resolved

import shutil
import os
import subprocess
from pathlib import Path

GMT_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.scenario_runner import ScenarioRunner
from lib import error_helpers
from lib.terminal_colors import TerminalColors
from lib.db import DB
from lib.global_config import GlobalConfig

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['run', 'website', 'ai'], nargs='?', default="run", help="Choose the mode - 'run' does a normal ScenarioRunner run where you can define --uri etc., 'website' quick measures a URL and 'ai' quickly measures a prompt")

    parser.add_argument('--name', type=str, help='A name which will be stored to the database to discern this run from others')

    parser.add_argument('--uri', type=str, help='The URI to get the usage_scenario.yml from. Can be either a local directory starting  with / or a remote git repository starting with http(s)://')
    parser.add_argument('--branch', type=str, help='Optionally specify the git branch when targeting a git repository')
    parser.add_argument('--filename', type=str, help='An optional alternative filename if you do not want to use "usage_scenario.yml"')

    parser.add_argument('--page', type=str, help='The URL to do a quick measurement of a website for (uses Firefox headless browser)')
    parser.add_argument('--prompt', type=str, help='The prompt to do a quick measurement of (uses gemma3:1b)')

    parser.add_argument('--user-id', type=int, default=1, help='A user-ID the run shall be mapped to. Defaults to 1 (the default user)')
    parser.add_argument('--config-override', type=str, help='Override the configuration file with the passed in yml file. Supply full path.')
    parser.add_argument('--file-cleanup', action='store_true', help='Delete all temporary files that the runner produced')
    parser.add_argument('--debug', action='store_true', help='Activate steppable debug mode')
    parser.add_argument('--allow-unsafe', action='store_true', help='Activate unsafe volume bindings, ports and complex environment vars')
    parser.add_argument('--skip-unsafe', action='store_true', help='Skip unsafe volume bindings, ports and complex environment vars')
    parser.add_argument('--skip-system-checks', action='store_true', help='Skip checking the system if the GMT can run')
    parser.add_argument('--verbose-provider-boot', action='store_true', help='Boot metric providers gradually')
    parser.add_argument('--full-docker-prune', action='store_true', help='Stop and remove all containers, build caches, volumes and images on the system')
    parser.add_argument('--docker-prune', action='store_true', help='Prune all unassociated build caches, networks volumes and stopped containers on the system')
    parser.add_argument('--skip-volume-inspect', action='store_true', help='Disable docker volume inspection. Can help if you encounter permission issues.')
    parser.add_argument('--dev-flow-timetravel', action='store_true', help='Allows to repeat a failed flow or timetravel to beginning of flows or restart services.')
    parser.add_argument('--dev-no-metrics', action='store_true', help='Skips loading the metric providers. Runs will be faster, but you will have no metric')
    parser.add_argument('--dev-no-sleeps', action='store_true', help='Removes all sleeps. Resulting measurement data will be skewed.')
    parser.add_argument('--dev-no-phase-stats', action='store_true', help='Do not calculate phase stats.')
    parser.add_argument('--dev-cache-build', action='store_true', help='Checks if a container image is already in the local cache and will then not build it. Also doesn\'t clear the images after a run. Please note that skipping builds only works the second time you make a run since the image has to be built at least initially to work.')
    parser.add_argument('--dev-no-optimizations', action='store_true', help='Disable analysis after run to find possible optimizations.')
    parser.add_argument('--print-phase-stats', type=str, help='Prints the stats for the given phase to the CLI for quick verification without the Dashboard. Try "[RUNTIME]" as argument.')
    parser.add_argument('--print-logs', action='store_true', help='Prints the container and process logs to stdout')

    args = parser.parse_args()

    if args.mode == 'website':

        if not args.page:
            parser.print_help()
            error_helpers.log_error('Please supply --page for quick measurement website mode to work')
            sys.exit(1)

        if args.page[0:7] != 'http:':
            print(TerminalColors.OKBLUE, 'Page hat no scheme. Adding https://', TerminalColors.ENDC)
            args.page = f"https://{args.page}"

        if args.filename or args.branch:
            parser.print_help()
            error_helpers.log_error('--branch or --filename are not allowed in website mode. Please remove or use run mode with a repository')
            sys.exit(1)

        args.uri = GMT_ROOT_DIR
        with open('templates/website/usage_scenario.yml', mode='r', encoding='utf-8') as f:
            usage_scenario = f.read()
            usage_scenario = usage_scenario.replace('__GMT_PLACEHOLDER_WEBSITE__', args.page)
        with open('templates/website/usage_scenario.yml.tmp', mode='w+', encoding='utf-8') as f:
            f.write(usage_scenario)
        args.filename = 'templates/website/usage_scenario.yml.tmp'
        run_type = 'folder'
        commit_hash_folder = 'templates/website/'

    elif args.mode == 'ai':
        if not args.prompt:
            parser.print_help()
            error_helpers.log_error('Please supply --prompt for quick measurement ai mode to work ')
            sys.exit(1)

        if args.filename or args.branch:
            parser.print_help()
            error_helpers.log_error('--branch or --filename are not allowed in website mode. Please remove or use run mode with a repository')
            sys.exit(1)

        args.uri = GMT_ROOT_DIR
        args.filename = 'templates/ai/usage_scenario.yml'
        run_type = 'folder'
        commit_hash_folder = 'templates/ai/'


    else:
        commit_hash_folder = GMT_ROOT_DIR

        if not args.filename:
            args.filename = 'usage_scenario.yml' # we do not want to use ArgumentParser default switch as we need to know if it was supplied for quick measurement overload check

        if args.uri is None:
            parser.print_help()
            error_helpers.log_error('Please supply --uri to get usage_scenario.yml from')
            sys.exit(1)

        if args.uri[0:8] == 'https://' or args.uri[0:7] == 'http://':
            print(TerminalColors.OKBLUE, '\nDetected supplied URL: ', args.uri, TerminalColors.ENDC)
            run_type = 'URL'
        elif args.uri[0:1] == '/':
            print(TerminalColors.OKBLUE, '\nDetected supplied folder: ', args.uri, TerminalColors. ENDC)
            run_type = 'folder'
            if not Path(args.uri).is_dir():
                parser.print_help()
                error_helpers.log_error('Could not find folder on local system. Please double check: ', uri=args.uri)
                sys.exit(1)
        else:
            parser.print_help()
            error_helpers.log_error('Could not detected correct URI. Please use local folder in Linux format /folder/subfolder/... or URL http(s):// : ', uri=args.uri)
            sys.exit(1)

    if args.allow_unsafe and args.skip_unsafe:
        parser.print_help()
        error_helpers.log_error('--allow-unsafe and skip--unsafe in conjuction is not possible')
        sys.exit(1)

    if args.dev_cache_build and (args.docker_prune or args.full_docker_prune):
        parser.print_help()
        error_helpers.log_error('--dev-cache-build blocks pruning docker images. Combination is not allowed')
        sys.exit(1)

    if args.full_docker_prune and GlobalConfig().config['postgresql']['host'] == 'green-coding-postgres-container':
        parser.print_help()
        error_helpers.log_error('--full-docker-prune is set while your database host is "green-coding-postgres-container".\nThe switch is only for remote measuring machines. It would stop the GMT images itself when running locally')
        sys.exit(1)

    if args.config_override is not None:
        if args.config_override[-4:] != '.yml':
            parser.print_help()
            error_helpers.log_error('Config override file must be a yml file')
            sys.exit(1)
        GlobalConfig(config_location=args.config_override)

    runner = ScenarioRunner(name=args.name, uri=args.uri, uri_type=run_type, filename=args.filename,
                    branch=args.branch, debug_mode=args.debug, allow_unsafe=args.allow_unsafe,
                    skip_system_checks=args.skip_system_checks,
                    skip_unsafe=args.skip_unsafe,verbose_provider_boot=args.verbose_provider_boot,
                    full_docker_prune=args.full_docker_prune, dev_no_sleeps=args.dev_no_sleeps,
                    dev_cache_build=args.dev_cache_build, dev_no_metrics=args.dev_no_metrics,
                    dev_flow_timetravel=args.dev_flow_timetravel, dev_no_optimizations=args.dev_no_optimizations,
                    docker_prune=args.docker_prune, dev_no_phase_stats=args.dev_no_phase_stats, user_id=args.user_id,
                    skip_volume_inspect=args.skip_volume_inspect, commit_hash_folder=commit_hash_folder)

    # Using a very broad exception makes sense in this case as we have excepted all the specific ones before
    #pylint: disable=broad-except
    try:
        run_id = runner.run()  # Start main code

        # this code can live at a different position.
        # From a user perspective it makes perfect sense to run both jobs directly after each other
        # In a cloud setup it however makes sense to free the measurement machine as soon as possible
        # So this code should be individually callable, separate from the runner

        if not runner._dev_no_optimizations:
            import optimization_providers.base  # We need to import this here as we need the correct config file
            print(TerminalColors.HEADER, '\nImporting optimization reporters ...', TerminalColors.ENDC)
            optimization_providers.base.import_reporters()

            print(TerminalColors.HEADER, '\nRunning optimization reporters ...', TerminalColors.ENDC)

            optimization_providers.base.run_reporters(runner._user_id, runner._run_id, runner._tmp_folder, runner.get_optimizations_ignore())

        if args.file_cleanup:
            shutil.rmtree(runner._tmp_folder)

        print(TerminalColors.OKGREEN,'\n\n####################################################################################')
        print(f"Please access your report on the URL {GlobalConfig().config['cluster']['metrics_url']}/stats.html?id={runner._run_id}")
        print('####################################################################################\n\n', TerminalColors.ENDC)


        if args.print_phase_stats:
            data = DB().fetch_all('SELECT metric, detail_name, value, type, unit FROM phase_stats WHERE run_id = %s and phase LIKE %s ', params=(runner._run_id, f"%{args.print_phase_stats}"))
            print(f"Data for phase {args.print_phase_stats}")
            for el in data:
                print(el)
            print('')

    except FileNotFoundError as e:
        error_helpers.log_error('File or executable not found', exception=e, previous_exception=e.__context__, run_id=runner._run_id)
    except subprocess.CalledProcessError as e:
        error_helpers.log_error('Command failed', stdout=e.stdout, stderr=e.stderr, previous_exception=e.__context__, run_id=runner._run_id)
    except RuntimeError as e:
        error_helpers.log_error('RuntimeError occured in runner.py', exception=e, previous_exception=e.__context__, run_id=runner._run_id)
    except BaseException as e:
        error_helpers.log_error('Base exception occured in runner.py', exception=e, previous_exception=e.__context__, run_id=runner._run_id)
    finally:
        if args.print_logs:
            for container_id_outer, std_out in runner.get_logs().items():
                print(f"Container logs of '{container_id_outer}':")
                print(std_out)
                print('\n-----------------------------\n')

        # Last thing before we exit is to shutdown the DB Pool
        DB().shutdown()
