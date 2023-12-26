#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

from lib.venv_checker import check_venv
check_venv() # this check must even run before __main__ as imports might not get resolved

import subprocess
import os
import sys
from pathlib import Path


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib import error_helpers
from lib.terminal_colors import TerminalColors
from lib.global_config import GlobalConfig


from runner import Runner

class Monitor(Runner):

    def __init__(self,
        name, debug_mode=False, trigger=None,
        no_file_cleanup=False, skip_system_checks=False,
        verbose_provider_boot=False,
        ):

        super().__init__(name=name, uri='http://metrics.green-coding.internal:9142/', uri_type=None, filename='not-set', branch='not-set',
            debug_mode=False, allow_unsafe=False, no_file_cleanup=False, skip_system_checks=False,
            skip_unsafe=False, verbose_provider_boot=False, full_docker_prune=False,
            dry_run=False, dev_repeat_run=False, docker_prune=False, job_id=None
        )

    def monitor(self):
        '''
            The run function is just a wrapper for the intended sequential flow of a GMT run.
            Mainly designed to call the functions individually for testing, but also
            if the flow ever needs to repeat certain blocks.

            The runner is to be thought of as a state machine.

            Methods thus will behave differently given the runner was instantiated with different arguments.

        '''
        try:
            config = GlobalConfig().config
            self.check_system('start')
            # self.initialize_folder(self._tmp_folder)
            # self.checkout_repository()
            self.initialize_run()
            #self.initial_parse()
            self.import_metric_providers()
            #self.populate_image_names()
            self.prepare_docker()
            # self.check_running_containers()
            # self.remove_docker_images()
            # self.download_dependencies()
            self.register_machine_id()
            self.update_and_insert_specs()
            if self._debugger.active:
                self._debugger.pause('Initial load complete. Waiting to start metric providers')

            self.start_metric_providers(allow_other=True, allow_container=False)
            if self._debugger.active:
                self._debugger.pause('metric-providers (non-container) start complete. Waiting to start measurement')

            self.custom_sleep(config['measurement']['idle-time-start'])

            self.start_measurement()

            self.start_metric_providers(allow_container=True, allow_other=False)

            self.start_phase('MOCK_BASELINE', transition=False, silent=True)
            self.end_phase('MOCK_BASELINE')

            self.start_phase('MOCK_INSTALLATION', transition=False, silent=True)
            self.end_phase('MOCK_INSTALLATION')

            self.start_phase('MOCK_BOOT', transition=False, silent=True)
            self.end_phase('MOCK_BOOT')

            self.start_phase('MOCK_IDLE', transition=False, silent=True)
            self.end_phase('MOCK_IDLE')


            self.start_phase('[RUNTIME]')
                # TODO: Trigger
            self.custom_sleep(2)



        except BaseException as exc:
            self.add_to_log(exc.__class__.__name__, str(exc))
            raise exc
        finally:
            self.end_phase('[RUNTIME]')
            self.end_measurement()
            self.store_phases()
            self.update_start_and_end_times()

            try:
                self.read_container_logs()
            except BaseException as exc:
                self.add_to_log(exc.__class__.__name__, str(exc))
                raise exc
            finally:
                try:
                    self.read_and_cleanup_processes()
                except BaseException as exc:
                    self.add_to_log(exc.__class__.__name__, str(exc))
                    raise exc
                finally:
                    try:
                        self.save_notes_runner()
                    except BaseException as exc:
                        self.add_to_log(exc.__class__.__name__, str(exc))
                        raise exc
                    finally:
                        try:
                            self.stop_metric_providers()
                        except BaseException as exc:
                            self.add_to_log(exc.__class__.__name__, str(exc))
                            raise exc
                        finally:
                            try:
                                self.save_stdout_logs()
                            except BaseException as exc:
                                self.add_to_log(exc.__class__.__name__, str(exc))
                                raise exc
                            finally:
                                self.cleanup()  # always run cleanup automatically after each run

        return self._run_id

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--name', type=str, help='A name which will be stored to the database to discern this run from others')
    parser.add_argument('--filename', type=str, default='usage_scenario.yml', help='An optional alternative filename if you do not want to use "usage_scenario.yml"')
    parser.add_argument('--config-override', type=str, help='Override the configuration file with the passed in yml file. Must be located in the same directory as the regular configuration file. Pass in only the name.')
    parser.add_argument('--no-file-cleanup', action='store_true', help='Do not delete files in /tmp/green-metrics-tool')
    parser.add_argument('--debug', action='store_true', help='Activate steppable debug mode')
    parser.add_argument('--allow-unsafe', action='store_true', help='Activate unsafe volume bindings, ports and complex environment vars')
    parser.add_argument('--skip-unsafe', action='store_true', help='Skip unsafe volume bindings, ports and complex environment vars')
    parser.add_argument('--skip-system-checks', action='store_true', help='Skip checking the system if the GMT can run')
    parser.add_argument('--verbose-provider-boot', action='store_true', help='Boot metric providers gradually')
    parser.add_argument('--full-docker-prune', action='store_true', help='Stop and remove all containers, build caches, volumes and images on the system')
    parser.add_argument('--docker-prune', action='store_true', help='Prune all unassociated build caches, networks volumes and stopped containers on the system')
    parser.add_argument('--dry-run', action='store_true', help='Removes all sleeps. Resulting measurement data will be skewed.')
    parser.add_argument('--dev-repeat-run', action='store_true', help='Checks if a docker image is already in the local cache and will then not build it. Also doesn\'t clear the images after a run')
    parser.add_argument('--print-logs', action='store_true', help='Prints the container and process logs to stdout')

    args = parser.parse_args()


    if args.name is None:
        parser.print_help()
        error_helpers.log_error('Please supply --name')
        sys.exit(1)


    if args.config_override is not None:
        if args.config_override[-4:] != '.yml':
            parser.print_help()
            error_helpers.log_error('Config override file must be a yml file')
            sys.exit(1)
        if not Path(f"{CURRENT_DIR}/{args.config_override}").is_file():
            parser.print_help()
            error_helpers.log_error(f"Could not find config override file on local system. Please double check: {CURRENT_DIR}/{args.config_override}")
            sys.exit(1)
        GlobalConfig(config_name=args.config_override)

    monitor = Monitor(
        args.name, debug_mode=args.debug, trigger=None,
        no_file_cleanup=args.no_file_cleanup, skip_system_checks=args.skip_system_checks,
        verbose_provider_boot=args.verbose_provider_boot,
    )

    # Using a very broad exception makes sense in this case as we have excepted all the specific ones before
    #pylint: disable=broad-except
    try:
        monitor.monitor()  # Start main code

        # this code should live at a different position.
        # From a user perspective it makes perfect sense to run both jobs directly after each other
        # In a cloud setup it however makes sense to free the measurement machine as soon as possible
        # So this code should be individually callable, separate from the monitor

        print(TerminalColors.HEADER, '\nCalculating and storing phases data. This can take a couple of seconds ...', TerminalColors.ENDC)

        # get all the metrics from the measurements table grouped by metric
        # loop over them issueing separate queries to the DB
        from tools.phase_stats import build_and_store_phase_stats

        print("Run id is", monitor._run_id)
        build_and_store_phase_stats(monitor._run_id, monitor._sci)


        print(TerminalColors.OKGREEN,'\n\n####################################################################################')
        print(f"Please access your report on the URL {GlobalConfig().config['cluster']['metrics_url']}/stats.html?id={monitor._run_id}")
        print('####################################################################################\n\n', TerminalColors.ENDC)

    except FileNotFoundError as e:
        error_helpers.log_error('File or executable not found', e, monitor._run_id)
    except subprocess.CalledProcessError as e:
        error_helpers.log_error('Command failed', 'Stdout:', e.stdout, 'Stderr:', e.stderr, monitor._run_id)
    except RuntimeError as e:
        error_helpers.log_error('RuntimeError occured in monitor.py: ', e, monitor._run_id)
    except BaseException as e:
        error_helpers.log_error('Base exception occured in monitor.py: ', e, monitor._run_id)
    finally:
        if args.print_logs:
            for container_id_outer, std_out in monitor.get_logs().items():
                print(f"Container logs of '{container_id_outer}':")
                print(std_out)
                print('\n-----------------------------\n')
