#!/usr/bin/env python3

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)

from lib.venv_checker import check_venv
check_venv()

import argparse
import importlib
import os
import shutil
import subprocess

from lib import error_helpers
from lib import process_helpers
from lib import utils
from lib.db import DB
from lib.global_config import GlobalConfig, freeze_dict
from lib.log_types import LogType
from lib.scenario_runner import ScenarioRunner, arrows
from lib.terminal_colors import TerminalColors


def _trim_cell(value, width):
    text = "" if value is None else str(value)
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def _print_simple_table(headers, rows):
    if not rows:
        print("No rows to display")
        return

    max_widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            max_widths[idx] = min(max(max_widths[idx], len("" if cell is None else str(cell))), 60)

    def fmt(row):
        return " | ".join(_trim_cell(cell, max_widths[idx]).ljust(max_widths[idx]) for idx, cell in enumerate(row))

    print(fmt(headers))
    print("-+-".join("-" * w for w in max_widths))
    for row in rows:
        print(fmt(row))


def print_shell_phase_stats_table(run_id):
    phase_row = DB().fetch_one(
        """
        SELECT phase
        FROM phase_stats
        WHERE run_id = %s AND hidden IS FALSE AND phase LIKE %s
        ORDER BY phase ASC
        LIMIT 1
        """,
        params=(run_id, "%_shell"),
    )

    if not phase_row:
        phase_row = DB().fetch_one(
            """
            SELECT phase
            FROM phase_stats
            WHERE run_id = %s AND hidden IS FALSE
            ORDER BY phase ASC
            LIMIT 1
            """,
            params=(run_id,),
        )

    if not phase_row:
        print("No phase stats found for this run.")
        return

    phase_name = phase_row[0]
    rows = DB().fetch_all(
        """
        SELECT metric, detail_name, type, value, unit, max_value, min_value
        FROM phase_stats
        WHERE run_id = %s AND phase = %s AND hidden IS FALSE
        ORDER BY metric ASC, detail_name ASC, type ASC
        """,
        params=(run_id, phase_name),
    )

    print(TerminalColors.OKGREEN, f"\nPhase stats summary:", TerminalColors.ENDC)

    _print_simple_table(
        ["metric", "detail", "type", "value", "unit", "max", "min"],
        rows,
    )


def ensure_runtime_phase_alias_for_shell_run(run_id):
    runtime_exists = DB().fetch_one(
        """
        SELECT 1
        FROM phase_stats
        WHERE run_id = %s AND phase LIKE %s
        LIMIT 1
        """,
        params=(run_id, "%_[RUNTIME]"),
    )
    if runtime_exists:
        return False

    source_phase_row = DB().fetch_one(
        """
        SELECT phase
        FROM phase_stats
        WHERE run_id = %s AND hidden IS FALSE AND phase LIKE %s
        ORDER BY phase ASC
        LIMIT 1
        """,
        params=(run_id, "%_shell"),
    )
    if not source_phase_row:
        source_phase_row = DB().fetch_one(
            """
            SELECT phase
            FROM phase_stats
            WHERE run_id = %s AND hidden IS FALSE AND phase NOT LIKE '%%[%%'
            ORDER BY phase ASC
            LIMIT 1
            """,
            params=(run_id,),
        )
    if not source_phase_row:
        return False

    source_phase = source_phase_row[0]
    prefix = source_phase.split("_", maxsplit=1)[0] if "_" in source_phase else "000"
    runtime_phase = f"{prefix}_[RUNTIME]"

    DB().query(
        """
        INSERT INTO phase_stats
            (run_id, metric, detail_name, phase, value, type, max_value, min_value,
             sampling_rate_avg, sampling_rate_max, sampling_rate_95p, unit, hidden, created_at)
        SELECT
            run_id, metric, detail_name, %s, value, type, max_value, min_value,
            sampling_rate_avg, sampling_rate_max, sampling_rate_95p, unit, hidden, NOW()
        FROM phase_stats
        WHERE run_id = %s AND phase = %s
        """,
        params=(runtime_phase, run_id, source_phase),
    )
    return True


class ShellScenarioRunner(ScenarioRunner):
    """Shell-only runner that reuses GMT measurement lifecycle without Docker scenario orchestration."""

    def _import_metric_providers(self):
        print(TerminalColors.HEADER, "\nImporting metric providers (shell mode)", TerminalColors.ENDC)

        if self._dev_no_metrics:
            print("Skipping import of metric providers due to --dev-no-metrics")
            return

        config = GlobalConfig().config
        metric_providers = utils.get_metric_providers(config, self._disabled_metric_providers)

        if not metric_providers:
            print(TerminalColors.WARNING, arrows("No metric providers were configured in config.yml. Was this intentional?"), TerminalColors.ENDC)
            return

        self._initialize_folder(self._metrics_folder)

        imported_any = False
        for metric_provider, conf in metric_providers.items():
            if ".container." in metric_provider or "network.connections.tcpdump.system" in metric_provider:
                print(f"Skipping container-oriented metric provider in shell mode: {metric_provider}")
                continue

            module_path, class_name = metric_provider.rsplit(".", 1)
            module_path = f"metric_providers.{module_path}"

            print(f"Importing {class_name} from {module_path}")
            module = importlib.import_module(module_path)

            if self._dev_no_system_checks:
                metric_provider_obj = getattr(module, class_name)(**(conf or {}), folder=self._metrics_folder, skip_check=True)
            else:
                metric_provider_obj = getattr(module, class_name)(**(conf or {}), folder=self._metrics_folder)

            self._ScenarioRunner__metric_providers.append(metric_provider_obj)
            imported_any = True

        if not imported_any:
            print(TerminalColors.WARNING, arrows("After filtering container providers, no shell-compatible metric providers remained."), TerminalColors.ENDC)

        self._ScenarioRunner__metric_providers.sort(key=lambda item: "rapl" not in item.__class__.__name__.lower())

    def cleanup(self):
        """Shell-safe cleanup that avoids Docker teardown calls."""
        print(TerminalColors.OKCYAN, "\nStarting shell cleanup routine", TerminalColors.ENDC)

        for metric_provider in list(self._ScenarioRunner__metric_providers):
            try:
                metric_provider.stop_profiling()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                error_helpers.log_error(f"Could not stop profiling on {metric_provider.__class__.__name__}", exception=exc)
        self._ScenarioRunner__metric_providers.clear()

        for ps in list(self._ScenarioRunner__ps_to_kill):
            try:
                process_helpers.kill_pg(ps["ps"], ps["cmd"])
            except ProcessLookupError:
                pass
            except Exception as exc:  # pylint: disable=broad-exception-caught
                error_helpers.log_error("Could not stop background process in shell cleanup", exception=exc)
        self._ScenarioRunner__ps_to_kill.clear()
        self._ScenarioRunner__ps_to_read.clear()

        print(TerminalColors.OKBLUE, "-Shell cleanup completed", TerminalColors.ENDC)

    def _run_shell_command(self, command, shell_executable):
        print(TerminalColors.HEADER, "\nExecuting shell command", TerminalColors.ENDC)
        print(command)

        ps = subprocess.run(
            [shell_executable, "-lc", command],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="UTF-8",
            errors="replace",
            timeout=self._measurement_total_duration,
        )

        if ps.stdout:
            print(ps.stdout, end="" if ps.stdout.endswith("\n") else "\n")
        if ps.stderr:
            print(ps.stderr, file=sys.stderr, end="" if ps.stderr.endswith("\n") else "\n")

        self._add_to_current_run_log(
            container_name="[SHELL]",
            log_type=LogType.FLOW_COMMAND,
            log_id=id(ps),
            cmd=[shell_executable, "-lc", command],
            phase="shell",
            stdout=ps.stdout,
            stderr=ps.stderr,
            flow="shell",
        )

        if ps.returncode != 0:
            raise subprocess.CalledProcessError(ps.returncode, [shell_executable, "-lc", command], output=ps.stdout, stderr=ps.stderr)

    def run_shell(self, command, shell_executable="bash"):
        self._arguments["shell_command"] = command
        self._arguments["shell_executable"] = shell_executable
        self._usage_scenario_original = freeze_dict({"type": "shell", "command": command})

        if not self._branch:
            self._branch = "[SHELL]"

        try:
            self._run_id = None
            self._create_folders()
            self._start_measurement()
            self._register_machine_id()
            self._import_metric_providers()
            self._initialize_run()

            self._start_metric_providers(allow_other=True, allow_container=False)
            self._start_phase("shell", transition=False)
            self._run_shell_command(command, shell_executable)
            self._end_phase("shell")

            self._end_measurement()

        except BaseException as exc:
            self._add_to_current_run_log(
                container_name="[SYSTEM]",
                log_type=LogType.EXCEPTION,
                log_id=id(exc),
                cmd="run_shell",
                phase="shell",
                stderr=f"{str(exc)}\n\n{exc.stderr}" if hasattr(exc, "stderr") else str(exc),
                stdout=exc.stdout if hasattr(exc, "stdout") else None,
                exception_class=exc.__class__.__name__,
            )
            self._set_run_failed()
            raise
        finally:
            try:
                self._post_process(0)
            finally:
                self.cleanup()

        print(TerminalColors.OKGREEN, arrows("SHELL MEASUREMENT SUCCESSFULLY COMPLETED"), TerminalColors.ENDC)
        return self._run_id


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run a single shell command under GMT metric collection (shell mode).",
        epilog='Use `--` before the command when the command contains options or shell operators. Example: ./shell.py -- \'echo "Hello" && sleep 10\'',
    )

    parser.add_argument("--name", type=str, help="Optional run name stored in DB")
    parser.add_argument("--user-id", type=int, default=1, help="User ID to map this run to (default: 1)")
    parser.add_argument("--config-override", type=str, help="Override config file with the passed yml file (full path)")
    parser.add_argument("--file-cleanup", action="store_true", help="Delete GMT temporary files after the run")
    parser.add_argument("--verbose-provider-boot", action="store_true", help="Boot metric providers gradually")
    parser.add_argument("--no-phase-padding", action="store_true", help="Disable phase end padding")
    parser.add_argument("--shell-executable", type=str, default="bash", help="Shell used to execute the command (default: bash)")

    parser.add_argument("--dev-no-metrics", action="store_true", help="Skip loading metric providers")
    parser.add_argument("--dev-no-phase-stats", action="store_true", help="Do not calculate phase stats")
    parser.add_argument("--dev-no-save", action="store_true", help="Do not write run or metrics to DB")

    parser.add_argument("--measurement-total-duration", type=int, default=None, help="Maximum runtime of the shell command in seconds")

    args, command_parts = parser.parse_known_args()
    if command_parts and command_parts[0] == "--":
        command_parts = command_parts[1:]
    if not command_parts:
        parser.print_help()
        raise SystemExit(1)

    args.command = " ".join(command_parts)
    return args


def main():
    args = parse_args()
    runner = None

    if args.config_override is not None:
        if not args.config_override.endswith(".yml"):
            raise ValueError("Config override file must be a yml file")
        GlobalConfig(config_location=args.config_override)

    print(TerminalColors.WARNING, "\n####################################################################################")
    print(f"Please use the docker version for exact measurments on the cluser!")
    print("####################################################################################\n", TerminalColors.ENDC)


    try:
        runner = ShellScenarioRunner(
            name=args.name,
            uri=os.getcwd(),
            uri_type="folder",
            filename="shell-command",
            branch="[SHELL]",
            verbose_provider_boot=args.verbose_provider_boot,
            user_id=args.user_id,
            phase_padding=not args.no_phase_padding,
            measurement_total_duration=args.measurement_total_duration,
            skip_optimizations=True,
            dev_no_metrics=args.dev_no_metrics,
            dev_no_phase_stats=args.dev_no_phase_stats,
            dev_no_save=args.dev_no_save,
            dev_no_system_checks=True,
        )

        run_id = runner.run_shell(args.command, shell_executable=args.shell_executable)

        if args.file_cleanup:
            shutil.rmtree(runner._tmp_folder, ignore_errors=True)

        if args.dev_no_save:
            print(TerminalColors.OKGREEN, "\nRun finished | --dev-no-save was active and nothing was written to DB\n", TerminalColors.ENDC)
            return

        if not args.dev_no_phase_stats and not args.dev_no_metrics:
            ensure_runtime_phase_alias_for_shell_run(run_id)
            print_shell_phase_stats_table(run_id)


        print(TerminalColors.OKGREEN, "\n####################################################################################")
        print(f"Please access your report on the URL {GlobalConfig().config['cluster']['metrics_url']}/stats.html?id={run_id}")
        print("####################################################################################\n", TerminalColors.ENDC)


    except KeyboardInterrupt:
        pass
    except FileNotFoundError as exc:
        error_helpers.log_error("File or executable not found", exception_context=exc.__context__, final_exception=exc, run_id=runner._run_id if runner else None)
    except subprocess.CalledProcessError as exc:
        error_helpers.log_error(str(exc), stdout=exc.stdout, stderr=exc.stderr, exception_context=exc.__context__, run_id=runner._run_id if runner else None)
    except RuntimeError as exc:
        error_helpers.log_error("RuntimeError occured in shell.py", exception_context=exc.__context__, final_exception=exc, run_id=runner._run_id if runner else None)
    except BaseException as exc:
        error_helpers.log_error("Base exception occured in shell.py", exception_context=exc.__context__, final_exception=exc, run_id=runner._run_id if runner else None)
    finally:
        # Explicitly close the psycopg pool to avoid thread finalization warnings on interpreter shutdown.
        try:
            if hasattr(DB, "instance") and hasattr(DB.instance, "_pool"):
                DB.instance.shutdown()
        except BaseException:
            pass


if __name__ == "__main__":
    main()
