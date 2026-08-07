#!/usr/bin/env python3

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)

from lib.venv_checker import check_venv
check_venv()

import argparse
import os
import shutil
import subprocess

from copy import deepcopy
from pathlib import Path

from lib import error_helpers
from lib import host_platform
from lib import utils
from lib.db import DB
from lib.global_config import GlobalConfig
from lib.scenario_runner import ScenarioRunner
from lib.terminal_colors import TerminalColors

SHELL_FLOW_NAME = 'Shell Command'


def print_shell_phase_stats_table(run_id):
    rows = DB().fetch_all(
        """
        SELECT metric, detail_name, type, value, unit, max_value, min_value
        FROM phase_stats
        WHERE run_id = %s AND phase LIKE %s AND hidden IS FALSE
        ORDER BY metric ASC, detail_name ASC, type ASC
        """,
        params=(run_id, f"%_{SHELL_FLOW_NAME}"),
    )

    if not rows:
        print("No phase stats found for this run.")
        return

    print(TerminalColors.OKGREEN, "\nPhase stats summary:", TerminalColors.ENDC)

    utils.print_simple_table(
        ["metric", "detail", "type", "value", "unit", "max", "min"],
        rows,
    )


class ShellScenarioRunner(ScenarioRunner):
    """Runs a single shell command through the standard GMT measurement lifecycle.

    It constructs an in-memory usage scenario whose only flow runs directly on the
    host (container: null) and skips all Docker orchestration steps, so no Docker
    daemon is required. Host execution is permission gated - the executing user
    needs the 'host' orchestrator capability (granted to the DEFAULT local user).
    """

    def __init__(self, *, shell_command, shell_executable, **kwargs):
        super().__init__(
            uri=os.getcwd(),
            uri_type='folder',
            filename='shell-command',
            skip_download_dependencies=True, # dependencies are only needed for building containers
            **kwargs,
        )
        self.__shell_command = shell_command
        self.__shell_executable = shell_executable
        self._arguments['shell_command'] = shell_command
        self._arguments['shell_executable'] = shell_executable

    def _checkout_repository(self):
        print('Skipping repository checkout in shell mode')
        # pylint: disable=no-member,attribute-defined-outside-init # pylint cannot resolve the name mangled attributes of the parent class
        self._ScenarioRunner__clean_uri = self._uri
        self._ScenarioRunner__working_folder = self._repo_folder = Path(self._uri).resolve(strict=True)
        self._branch = '[SHELL]'

    def _load_yml_file(self):
        usage_scenario = {
            'name': self._name,
            'author': '[SHELL]',
            'description': f"Shell command executed via shell.py: {self.__shell_command}",
            'flow': [{
                'name': SHELL_FLOW_NAME,
                'container': None, # run directly on the host
                'commands': [{
                    'type': 'console',
                    'command': self.__shell_command,
                    'shell': self.__shell_executable,
                    'note': 'Starting shell command',
                }],
            }],
        }
        # pylint: disable=no-member # pylint cannot resolve the name mangled attribute of the parent class
        self._ScenarioRunner__usage_scenario.clear()
        self._ScenarioRunner__usage_scenario.update(usage_scenario)
        self._usage_scenario_original = deepcopy(usage_scenario)

    # Shell mode never has services, so all Docker interaction can be skipped.
    # This also allows running on machines that have no Docker installed at all.
    def _check_running_containers_before_start(self):
        print('Skipping check for running containers in shell mode')

    def _remove_docker_images(self):
        print('Skipping Docker image cleanup in shell mode')

    def _setup_networks(self):
        print('Skipping network setup in shell mode')


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run a single shell command under GMT metric collection (shell mode).",
        epilog='Use `--` before the command when the command contains options or shell operators. Example: ./shell.py -- \'echo "Hello" && sleep 10\'',
    )

    parser.add_argument("--name", type=str, help="Optional run name stored in DB")
    parser.add_argument("--user-id", type=int, default=1, help="User ID to map this run to (default: 1). The user needs the 'host' orchestrator capability.")
    parser.add_argument("--config-override", type=str, help="Override config file with the passed yml file (full path)")
    parser.add_argument("--file-cleanup", action="store_true", help="Delete GMT temporary files after the run")
    parser.add_argument("--verbose-provider-boot", action="store_true", help="Boot metric providers gradually")
    parser.add_argument("--shell-executable", type=str, default=None, help="Shell used to execute the command (default: bash; powershell on Windows)")

    parser.add_argument("--dev-no-metrics", action="store_true", help="Skip loading metric providers")
    parser.add_argument("--dev-no-phase-stats", action="store_true", help="Do not calculate phase stats")
    parser.add_argument("--dev-no-save", action="store_true", help="Do not write run or metrics to DB")
    parser.add_argument("--dev-no-sleeps", action="store_true", help="Removes all sleeps. Resulting measurement data will be skewed.")

    parser.add_argument("--measurement-flow-process-duration", type=int, default=None, help="Maximum runtime of the shell command in seconds")

    args, command_parts = parser.parse_known_args()

    # Unknown arguments become part of the shell command, so a mistyped flag would be silently
    # executed instead of rejected. Everything after an explicit `--` is always taken verbatim.
    explicit_separator = bool(command_parts) and command_parts[0] == "--"
    if explicit_separator:
        command_parts = command_parts[1:]
    elif command_parts and command_parts[0].startswith("-"):
        parser.error(f"unrecognized argument: {command_parts[0]}\nIf this was meant to be part of the command, put it after `--`: ./shell.py -- '{' '.join(command_parts)}'")

    if not command_parts:
        parser.print_help()
        raise SystemExit(1)

    if args.shell_executable is None:
        args.shell_executable = 'powershell' if host_platform.is_windows() else 'bash'

    args.command = " ".join(command_parts)
    return args


def _report_shell_error(*messages, persist=True, **kwargs):
    if persist:
        error_helpers.log_error(*messages, **kwargs)
        return

    error_message = error_helpers.format_error(*messages, **kwargs)
    print(TerminalColors.FAIL, error_message, TerminalColors.ENDC, file=sys.stderr)


def main():
    args = parse_args()
    runner = None

    if args.config_override is not None:
        if not args.config_override.endswith(".yml"):
            raise ValueError("Config override file must be a yml file")
        GlobalConfig(config_location=args.config_override)

    print(TerminalColors.WARNING, "\n####################################################################################")
    print("Please use the docker version for exact measurements on the cluster!")
    print("####################################################################################\n", TerminalColors.ENDC)


    try:
        runner = ShellScenarioRunner(
            name=args.name,
            shell_command=args.command,
            shell_executable=args.shell_executable,
            verbose_provider_boot=args.verbose_provider_boot,
            user_id=args.user_id,
            skip_optimizations=True,
            dev_no_metrics=args.dev_no_metrics,
            dev_no_phase_stats=args.dev_no_phase_stats,
            dev_no_save=args.dev_no_save,
            dev_no_sleeps=args.dev_no_sleeps,
            dev_no_system_checks=True,
            dev_no_container_dependency_collection=True,
            measurement_flow_process_duration=args.measurement_flow_process_duration,
            # shell mode is a quick tool - keep the measurement phases snappy compared to the runner defaults
            measurement_pre_test_sleep=1,
            measurement_baseline_duration=5,
            measurement_idle_duration=5,
            measurement_post_test_sleep=1,
        )

        run_id = runner.run()

        if args.file_cleanup:
            shutil.rmtree(runner._tmp_folder, ignore_errors=True)

        if args.dev_no_save:
            print(TerminalColors.OKGREEN, "\nRun finished | --dev-no-save was active and nothing was written to DB\n", TerminalColors.ENDC)
            return 0

        if not args.dev_no_phase_stats and not args.dev_no_metrics:
            print_shell_phase_stats_table(run_id)


        print(TerminalColors.OKGREEN, "\n####################################################################################")
        print(f"Please access your report on the URL {GlobalConfig().config['cluster']['metrics_url']}/stats.html?id={run_id}")
        print("####################################################################################\n", TerminalColors.ENDC)
        return 0


    except KeyboardInterrupt:
        return 130
    except FileNotFoundError as exc:
        _report_shell_error("File or executable not found", persist=not args.dev_no_save, exception_context=exc.__context__, final_exception=exc, run_id=runner._run_id if runner else None)
        return 127
    except subprocess.CalledProcessError as exc:
        _report_shell_error(str(exc), persist=not args.dev_no_save, stdout=exc.stdout, stderr=exc.stderr, exception_context=exc.__context__, run_id=runner._run_id if runner else None)
        return exc.returncode or 1
    except subprocess.TimeoutExpired as exc:
        _report_shell_error("Shell command timed out", persist=not args.dev_no_save, stdout=exc.stdout, stderr=exc.stderr, exception_context=exc.__context__, run_id=runner._run_id if runner else None)
        return 124
    except RuntimeError as exc:
        _report_shell_error("RuntimeError occurred in shell.py", persist=not args.dev_no_save, exception_context=exc.__context__, final_exception=exc, run_id=runner._run_id if runner else None)
        return 1
    except Exception as exc:  # pylint: disable=broad-exception-caught
        _report_shell_error("Exception occurred in shell.py", persist=not args.dev_no_save, exception_context=exc.__context__, final_exception=exc, run_id=runner._run_id if runner else None)
        return 1
    finally:
        # Explicitly close the psycopg pool to avoid thread finalization warnings on interpreter shutdown.
        try:
            if hasattr(DB, "instance") and hasattr(DB.instance, "_pool"):
                DB.instance.shutdown()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(TerminalColors.WARNING, f"Could not cleanly shut down DB pool: {exc}", TerminalColors.ENDC, file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
