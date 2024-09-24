#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

from lib.venv_checker import check_venv
check_venv() # this check must even run before __main__ as imports might not get resolved

import subprocess
import os
import sys
import time
from pathlib import Path
import shutil

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib import error_helpers
from lib.terminal_colors import TerminalColors
from lib.global_config import GlobalConfig


from runner import Runner

class Monitor(Runner):

    def __init__(self,
        name, debug_mode=False,
        skip_system_checks=False,
        verbose_provider_boot=False,
        ):

        super().__init__(name=name, uri='http://metrics.green-coding.internal:9142/', uri_type=None, filename='not-set', branch='not-set',
            debug_mode=debug_mode, skip_system_checks=skip_system_checks, verbose_provider_boot=verbose_provider_boot
        )

    def monitor(self):
        '''
            The run function is just a wrapper for the intended sequential flow of a GMT run.
            Mainly designed to call the functions individually for testing, but also
            if the flow ever needs to repeat certain blocks.

            The runner is to be thought of as a state machine.

            Methods thus will behave differently given the runner was instantiated with different arguments.

        '''
        runtime_phase_started = False
        try:
            config = GlobalConfig().config
            self.check_system('start')
            # self.initialize_folder(self._tmp_folder)
            # self.checkout_repository()
            self.initialize_run()
            #self.initial_parse()
            self.import_metric_providers(monitor=True)
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



            self.start_phase('[RUNTIME]', transition=False)
            runtime_phase_started = True
                # TODO: Trigger

            print('Monitoring active ... press CTRL+C to stop and save data.')
            while True:
                time.sleep(3600)



        except KeyboardInterrupt as exc:
            raise exc
        except BaseException as exc:
            self.add_to_log(exc.__class__.__name__, str(exc))
            self.set_run_failed()
            raise exc
        finally:
            try:

                if runtime_phase_started:
                    self.end_phase('[RUNTIME]')
                self.end_measurement()
                self.store_phases()
                self.update_start_and_end_times()
            except BaseException as exc:
                self.add_to_log(exc.__class__.__name__, str(exc))
                raise exc
            finally:
                self._handle_except()

        return self._run_id

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--name', type=str, help='A name which will be stored to the database to discern this run from others')
    parser.add_argument('--config-override', type=str, help='Override the configuration file with the passed in yml file. Must be located in the same directory as the regular configuration file. Pass in only the name.')
    parser.add_argument('--file-cleanup', action='store_true', help='Delete all temporary files that the runner produced')
    parser.add_argument('--debug', action='store_true', help='Activate steppable debug mode')
    parser.add_argument('--print-logs', action='store_true', help='Prints the container and process logs to stdout')
    parser.add_argument('--skip-system-checks', action='store_true', help='Skip checking the system if the GMT can run')
    parser.add_argument('--verbose-provider-boot', action='store_true', help='Boot metric providers gradually')

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

    runner = Monitor(
        args.name,
        debug_mode=args.debug,
        skip_system_checks=args.skip_system_checks,
    )

    # Using a very broad exception makes sense in this case as we have excepted all the specific ones before
    #pylint: disable=broad-except
    try:
        runner.monitor()  # Start main code

        # this code should live at a different position.
        # From a user perspective it makes perfect sense to run both jobs directly after each other
        # In a cloud setup it however makes sense to free the measurement machine as soon as possible
        # So this code should be individually callable, separate from the monitor

    except KeyboardInterrupt:
        print(TerminalColors.HEADER, '\nCalculating and storing phases data. This can take a couple of seconds ...', TerminalColors.ENDC)

        # get all the metrics from the measurements table grouped by metric
        # loop over them issuing separate queries to the DB
        from tools.phase_stats import build_and_store_phase_stats

        print("Run id is", runner._run_id)
        print("Aggregating and uploading phase_stats. This can take a while for longer runs ...")
        build_and_store_phase_stats(runner._run_id, runner._sci)

        if not runner._dev_no_optimizations:
            import optimization_providers.base
            print(TerminalColors.HEADER, '\nImporting optimization reporters ...', TerminalColors.ENDC)
            optimization_providers.base.import_reporters()

            print(TerminalColors.HEADER, '\nRunning optimization reporters ...', TerminalColors.ENDC)

            optimization_providers.base.run_reporters(runner._run_id, runner._tmp_folder, runner.get_optimizations_ignore())

        if args.file_cleanup:
            shutil.rmtree(runner._tmp_folder)

        print(TerminalColors.OKGREEN,'\n\n####################################################################################')
        print(f"Please access your report on the URL {GlobalConfig().config['cluster']['metrics_url']}/stats.html?id={runner._run_id}")
        print('####################################################################################\n\n', TerminalColors.ENDC)

    except FileNotFoundError as e:
        error_helpers.log_error('File or executable not found', exception=e, run_id=runner._run_id)
    except subprocess.CalledProcessError as e:
        error_helpers.log_error('Command failed', stdout=e.stdout, stderr=e.stderr, run_id=runner._run_id)
    except RuntimeError as e:
        error_helpers.log_error('RuntimeError occured in runner.py', exception=e, run_id=runner._run_id)
    except BaseException as e:
        error_helpers.log_error('Base exception occured in runner.py', exception=e, run_id=runner._run_id)
    finally:
        if args.print_logs:
            for container_id_outer, std_out in runner.get_logs().items():
                print(f"Container logs of '{container_id_outer}':")
                print(std_out)
                print('\n-----------------------------\n')
