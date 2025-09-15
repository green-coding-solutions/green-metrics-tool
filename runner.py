#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import glob
import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from lib.venv_checker import check_venv
check_venv() # this check must even run before __main__ as imports might not get resolved

import shutil
import os
import re
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

    parser.add_argument('--name', type=str, help='A name which will be stored to the database to discern this run from others')

    parser.add_argument('--uri', type=str, help='The URI to get the usage_scenario.yml from. Can be either a local directory starting  with / or a remote git repository starting with http(s)://')
    parser.add_argument('--branch', type=str, help='Optionally specify the git branch when targeting a git repository')
    parser.add_argument('--filename', type=str, action='append', help='An optional alternative filename if you do not want to use "usage_scenario.yml". Multiple filenames can be provided (e.g. "--filename usage_scenario_1.yml --filename usage_scenario_2.yml"). Paths like ../usage_scenario.yml and wildcards like *.yml are supported. Duplicate filenames are allowed and will be processed multiple times.')

    parser.add_argument('--variables', nargs='+', help='Variables that will be replaced into the usage_scenario.yml file')
    parser.add_argument('--commit-hash-folder', help='Use a different folder than the repository root to determine the commit hash for the run')

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
    parser.add_argument('--no-phase-padding', action='store_true', help='Do not add paddings to phase end to capture incomplete last sampling interval.')
    parser.add_argument('--dev-flow-timetravel', action='store_true', help='Allows to repeat a failed flow or timetravel to beginning of flows or restart services.')
    parser.add_argument('--dev-no-metrics', action='store_true', help='Skips loading the metric providers. Runs will be faster, but you will have no metric')
    parser.add_argument('--dev-no-sleeps', action='store_true', help='Removes all sleeps. Resulting measurement data will be skewed.')
    parser.add_argument('--dev-no-phase-stats', action='store_true', help='Do not calculate phase stats.')
    parser.add_argument('--dev-cache-build', action='store_true', help='Checks if a container image is already in the local cache and will then not build it. Also doesn\'t clear the images after a run. Please note that skipping builds only works the second time you make a run since the image has to be built at least initially to work.')
    parser.add_argument('--dev-no-optimizations', action='store_true', help='Disable analysis after run to find possible optimizations.')
    parser.add_argument('--dev-no-save', action='store_true', help='Will save no data to the DB. This implicitly activates --dev-no-phase-stats, --dev-no-metrics and --dev-no-optimizations')
    parser.add_argument('--print-phase-stats', type=str, help='Prints the stats for the given phase to the CLI for quick verification without the Dashboard. Try "[RUNTIME]" as argument.')
    parser.add_argument('--print-logs', action='store_true', help='Prints the container and process logs to stdout')
    parser.add_argument('--iterations', type=int, default=1, help='Specify how many times each scenario should be run. Default is 1. With multiple files, all files are processed sequentially, then the entire sequence is repeated N times. Example: with files A.yml, B.yml and --iterations 2, the execution order is A, B, A, B.')


    # Measurement settings
    parser.add_argument('--measurement-system-check-threshold', type=int, default=3, help='System check threshold when to issue warning and when to fail. When set on 3 runs will fail only on erros, when 2 then also on warnings and 1 also on pure info statements. Can be 1=INFO, 2=WARN or 3=ERROR')
    parser.add_argument('--measurement-pre-test-sleep', type=int, default=5, help='Override measurement pre-test sleep')
    parser.add_argument('--measurement-idle-duration', type=int, default=60, help='Override measurement idle duration')
    parser.add_argument('--measurement-baseline-duration', type=int, default=60, help='Override measurement baseline duration')
    parser.add_argument('--measurement-post-test-sleep', type=int, default=5, help='Override measurement post-test sleep')
    parser.add_argument('--measurement-phase-transition-time', type=int, default=1, help='Override measurement phase transition time')
    parser.add_argument('--measurement-wait-time-dependencies', type=int, default=60, help='Override measurement wait time for dependencies')
    parser.add_argument('--measurement-flow-process-duration', type=int, default=86400, help='Override measurement flow process duration')
    parser.add_argument('--measurement-total-duration', type=int, default=86400, help='Override measurement total duration')

    # intentionally not supported
    # parser.add_argument('--disabled-metric-providers', nargs='+', help='Override disabled metric providers') # user can just edit the config in CLI mode and using another args="+" for parsing CLI is flaky
    # parser.add_argument('--allowed-run-args', nargs='+', help='Override allowed run arguments to be passed to the docker container') # user can just go into --allow-unsafe and using another args="+" for parsing CLI is flaky

    args = parser.parse_args()

    if args.uri is None:
        parser.print_help()
        error_helpers.log_error('Please supply --uri to get usage_scenario.yml from')
        sys.exit(1)

    if args.uri[0:8] == 'https://' or args.uri[0:7] == 'http://':
        print(TerminalColors.OKBLUE, '\nDetected supplied URL: ', args.uri, TerminalColors.ENDC)
        run_type = 'URL'
    elif args.uri[0:1] == '/':
        print(TerminalColors.OKBLUE, '\nDetected supplied folder: ', args.uri, TerminalColors.ENDC)
        run_type = 'folder'
        if not Path(args.uri).is_dir():
            parser.print_help()
            error_helpers.log_error('Could not find folder on local system. Please double check: ', uri=args.uri)
            sys.exit(1)
    else:
        parser.print_help()
        error_helpers.log_error('Could not detected correct URI. Please use local folder in Linux format /folder/subfolder/... or URL http(s):// : ', uri=args.uri)
        sys.exit(1)

    variables_dict = {}
    if args.variables:
        for var in args.variables:
            if not re.fullmatch(r'__GMT_VAR_[\w]+__=.*', var):
                raise ValueError(f"Usage Scenario variable ({var}) has invalid name. Format must be __GMT_VAR_[\\w]+__. Example: __GMT_VAR_EXAMPLE__")
            key, value = var.split('=', maxsplit=1)
            variables_dict[key] = value

    if args.config_override is not None:
        if args.config_override[-4:] != '.yml':
            parser.print_help()
            error_helpers.log_error('Config override file must be a yml file')
            sys.exit(1)
        GlobalConfig(config_location=args.config_override)

    # Use default filename if none provided
    filename_patterns = args.filename if args.filename else ['usage_scenario.yml']
    using_default_filename = not args.filename

    filenames = []
    for pattern in filename_patterns:
        if run_type == 'folder':
            # For local directories, look for files relative to the URI path
            search_pattern = os.path.join(args.uri, pattern)
            matches = glob.glob(search_pattern)
            # Convert absolute paths back to relative paths for ScenarioRunner
            valid_files = []
            for match in matches:
                if os.path.isfile(match):
                    # Convert absolute path back to relative path
                    relative_path = os.path.relpath(match, args.uri)
                    valid_files.append(relative_path)

            if not valid_files:
                if using_default_filename:
                    print(TerminalColors.FAIL, f'Error: Default file not found: {pattern}. Search pattern: {search_pattern}', TerminalColors.ENDC)
                    print('Please create the file or specify a different file with --filename')
                else:
                    print(TerminalColors.FAIL, f'Error: No valid files found for --filename pattern: {pattern}. Search pattern: {search_pattern}', TerminalColors.ENDC)
                sys.exit(1)
            filenames.extend(valid_files)
        else:
            # For URLs, file validation will happen after checkout in ScenarioRunner
            # Just pass the pattern as-is since we can't validate files that don't exist locally yet
            filenames.append(pattern)

    # Execute the given usage scenarios multiple times (if iterations > 1)
    filenames = filenames * args.iterations

    # Create ScenarioRunner once and reuse it for all files
    runner = ScenarioRunner(name=args.name, uri=args.uri, uri_type=run_type, filename=filenames[0],
                    branch=args.branch, debug_mode=args.debug, allow_unsafe=args.allow_unsafe,
                    skip_system_checks=args.skip_system_checks,
                    skip_unsafe=args.skip_unsafe,verbose_provider_boot=args.verbose_provider_boot,
                    full_docker_prune=args.full_docker_prune, dev_no_sleeps=args.dev_no_sleeps,
                    dev_cache_build=args.dev_cache_build, dev_no_metrics=args.dev_no_metrics, dev_no_save=args.dev_no_save,
                    dev_flow_timetravel=args.dev_flow_timetravel, dev_no_optimizations=args.dev_no_optimizations,
                    docker_prune=args.docker_prune, dev_no_phase_stats=args.dev_no_phase_stats, user_id=args.user_id,
                    skip_volume_inspect=args.skip_volume_inspect, commit_hash_folder=args.commit_hash_folder,
                    usage_scenario_variables=variables_dict, phase_padding=not args.no_phase_padding,
                    measurement_system_check_threshold=args.measurement_system_check_threshold,
                    measurement_pre_test_sleep=args.measurement_pre_test_sleep,
                    measurement_idle_duration=args.measurement_idle_duration,
                    measurement_baseline_duration=args.measurement_baseline_duration,
                    measurement_post_test_sleep=args.measurement_post_test_sleep,
                    measurement_phase_transition_time=args.measurement_phase_transition_time,
                    measurement_wait_time_dependencies=args.measurement_wait_time_dependencies,
                    measurement_flow_process_duration=args.measurement_flow_process_duration,
                    measurement_total_duration=args.measurement_total_duration,
                    #disabled_metric_providers # this is intentionally not supported as the user can just edit the config in CLI mode and using another args="+" for parsing CLI is flaky
                    #allowed_run_args=user._capabilities['measurement']['orchestrators']['docker']['allowed_run_args'] # this is intentionally not supported as the user can just enter --allow-unsafe in CLI mode and using another args="+" for parsing CLI is flaky
                    )

    # Using a very broad exception makes sense in this case as we have excepted all the specific ones before
    #pylint: disable=broad-except
    try:
        for filename in filenames:
            print(TerminalColors.OKBLUE, '\nRunning: ', filename, TerminalColors.ENDC)

            # Update filename for reused runner (no-op for first file)
            runner.set_filename(filename)

            run_id = runner.run()  # Start main code

            # this code can live at a different position.
            # From a user perspective it makes perfect sense to run both jobs directly after each other
            # In a cloud setup it however makes sense to free the measurement machine as soon as possible
            # So this code should be individually callable, separate from the runner
            if not runner._dev_no_optimizations and not runner._dev_no_save:
                import optimization_providers.base  # We need to import this here as we need the correct config file
                print(TerminalColors.HEADER, '\nImporting optimization reporters ...', TerminalColors.ENDC)
                optimization_providers.base.import_reporters()
                print(TerminalColors.HEADER, '\nRunning optimization reporters ...', TerminalColors.ENDC)
                optimization_providers.base.run_reporters(runner._user_id, runner._run_id, runner._tmp_folder, runner.get_optimizations_ignore())

            if args.file_cleanup:
                shutil.rmtree(runner._tmp_folder)

            if not runner._dev_no_save:
                print(TerminalColors.OKGREEN,'\n\n####################################################################################')
                print(f"Please access your report on the URL {GlobalConfig().config['cluster']['metrics_url']}/stats.html?id={runner._run_id}")
                print('####################################################################################\n\n', TerminalColors.ENDC)

                if args.print_phase_stats:
                    phase_stats = DB().fetch_all('SELECT metric, detail_name, value, type, unit FROM phase_stats WHERE run_id = %s and phase LIKE %s ', params=(runner._run_id, f"%{args.print_phase_stats}"))
                    print(f"Data for phase {args.print_phase_stats}")
                    for el in phase_stats:
                        print(el)
                    print('')
            else:
                print(TerminalColors.OKGREEN,'\n\n####################################################################################')
                print('Run finished | --dev-no-save was active and nothing was written to DB')
                print('####################################################################################\n\n', TerminalColors.ENDC)

    except KeyboardInterrupt:
        pass
    except FileNotFoundError as e:
        error_helpers.log_error('File or executable not found', exception_context=e.__context__, final_exception=e, run_id=runner._run_id if runner else None)
    except subprocess.CalledProcessError as e:
        error_helpers.log_error('Command failed', stdout=e.stdout, stderr=e.stderr, exception_context=e.__context__, run_id=runner._run_id if runner else None)
    except RuntimeError as e:
        error_helpers.log_error('RuntimeError occured in runner.py', exception_context=e.__context__, final_exception=e, run_id=runner._run_id if runner else None)
    except BaseException as e:
        error_helpers.log_error('Base exception occured in runner.py', exception_context=e.__context__, final_exception=e, run_id=runner._run_id if runner else None)
    finally:
        if args.print_logs and runner:
            logs = runner._get_all_run_logs()
            if logs:
                print("Container logs:")
                for container_name, log_entries in logs.items():
                    print(f"=== {container_name} ===")
                    for log_entry in log_entries:
                        log_type = log_entry.get('type', 'unknown')
                        if "stdout" in log_entry:
                            print(f"STDOUT ({log_type}):\n{log_entry['stdout']}")
                        if "stderr" in log_entry:
                            print(f"STDERR ({log_type}):\n{log_entry['stderr']}")
                    print('-----------------------------')
                print()

        # Last thing before we exit is to shutdown the DB Pool
        DB().shutdown()
