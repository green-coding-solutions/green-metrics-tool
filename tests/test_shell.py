import json
import shlex
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import shell
from lib import scenario_runner
from lib.db import DB
from lib.scenario_runner import ScenarioRunner
from shell import ShellScenarioRunner
from tests import test_functions as Tests

GMT_DIR = Path(__file__).parent.parent.as_posix()


@pytest.fixture(autouse=True)
def setup_and_cleanup_test():
    """Keep these unit tests independent from the database-backed global fixture."""
    yield


def _main_args(**overrides):
    values = {
        "name": None,
        "config_override": None,
        "file_cleanup": False,
        "verbose_provider_boot": False,
        "shell_executable": "bash",
        "user_id": 1,
        "dev_no_metrics": True,
        "dev_no_phase_stats": True,
        "dev_no_save": True,
        "dev_no_sleeps": False,
        "measurement_flow_process_duration": 1,
        "command": "printf shell-wrapper-ok",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _make_runner(**overrides):
    values = {
        "shell_command": "echo 1",
        "shell_executable": "bash",
        "dev_no_save": True,
        "dev_no_metrics": True,
        "dev_no_system_checks": True,
        "skip_optimizations": True,
    }
    values.update(overrides)
    return ShellScenarioRunner(**values)


def test_shell_runner_builds_host_usage_scenario():
    runner = _make_runner(shell_command='echo "hello host"')
    runner._load_yml_file()

    scenario = getattr(runner, "_ScenarioRunner__usage_scenario")
    assert scenario["flow"][0]["container"] is None
    assert scenario["flow"][0]["name"] == shell.SHELL_FLOW_NAME
    assert scenario["flow"][0]["commands"][0] == {
        "type": "console",
        "command": 'echo "hello host"',
        "shell": "bash",
        "note": "Starting shell command",
    }
    assert runner._usage_scenario_original == scenario


def test_shell_runner_uses_current_metric_provider_importer(monkeypatch, tmp_path):
    provider_config = {"cpu_utilization_procfs_system": {"sampling_rate": 99}}
    imported_modules = []

    class FakeProvider:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    def fake_import_module(module_path):
        imported_modules.append(module_path)
        return SimpleNamespace(CpuUtilizationProcfsSystemProvider=FakeProvider)

    monkeypatch.setattr(
        scenario_runner.utils,
        "get_metric_providers",
        lambda _config, _disabled=None: provider_config,
    )
    monkeypatch.setattr(scenario_runner.importlib, "import_module", fake_import_module)

    runner = _make_runner(dev_no_metrics=False)
    runner._metrics_folder = tmp_path / "metrics"
    runner._import_metric_providers()

    providers = getattr(runner, "_ScenarioRunner__metric_providers")
    assert ShellScenarioRunner._import_metric_providers is ScenarioRunner._import_metric_providers
    assert imported_modules == ["metric_providers.cpu.utilization.procfs.system.provider"]
    assert len(providers) == 1
    assert providers[0].kwargs["sampling_rate"] == 99
    assert providers[0].kwargs["skip_check"] is True
    assert providers[0].kwargs["folder"] == runner._metrics_folder


def test_main_passes_command_and_timeout_to_runner(monkeypatch, tmp_path):
    calls = {}

    class FakeRunner:
        def __init__(self, **kwargs):
            calls["init"] = kwargs
            self._run_id = None
            self._tmp_folder = Path(tmp_path)

        def run(self):
            calls["run"] = True
            self._run_id = "fake-run-id"
            return self._run_id

    monkeypatch.setattr(shell, "parse_args", _main_args)
    monkeypatch.setattr(shell, "ShellScenarioRunner", FakeRunner)
    monkeypatch.setattr(shell, "DB", type("FakeDB", (), {}))

    assert shell.main() == 0
    assert calls["run"] is True
    assert calls["init"]["shell_command"] == "printf shell-wrapper-ok"
    assert calls["init"]["shell_executable"] == "bash"
    assert calls["init"]["measurement_flow_process_duration"] == 1
    assert calls["init"]["dev_no_sleeps"] is False
    assert calls["init"]["user_id"] == 1


# shell.py is a local operator tool. Running as a non-default user (a hidden cluster user for instance)
# must stay possible, so the user the 'host' capability is checked against is selectable.
def test_parse_args_user_id_defaults_to_the_default_user(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['shell.py', '--', 'echo 1'])

    assert shell.parse_args().user_id == 1


def test_parse_args_accepts_a_custom_user_id(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['shell.py', '--user-id', '22', '--', 'echo 1'])

    assert shell.parse_args().user_id == 22


# the raw command may contain anything the user typed, so it must not be duplicated into
# runs.runner_arguments where filter_sensitive_data() cannot redact it
def test_shell_runner_does_not_persist_the_command_in_runner_arguments():
    runner = _make_runner(shell_command='echo "hello host"')

    assert 'shell_command' not in runner._arguments
    assert 'shell_executable' not in runner._arguments
    assert 'echo "hello host"' not in json.dumps(runner._arguments)


def test_parse_args_passes_dev_no_sleeps(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['shell.py', '--dev-no-sleeps', 'echo', 'Hello'])

    args = shell.parse_args()

    assert args.dev_no_sleeps is True
    assert args.command == 'echo Hello'


def test_parse_args_rejects_mistyped_flag_instead_of_running_it(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['shell.py', '--dev-no-sleep-typo', 'echo', 'Hello'])

    with pytest.raises(SystemExit):
        shell.parse_args()

    assert 'unrecognized argument: --dev-no-sleep-typo' in capsys.readouterr().err


def test_parse_args_allows_flag_like_command_after_separator(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['shell.py', '--', '--flag-like-command', 'arg'])

    args = shell.parse_args()

    assert args.command == '--flag-like-command arg'


# a single argument is a shell snippet and must reach the shell exactly as written
def test_parse_args_takes_a_single_argument_verbatim(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['shell.py', '--', 'echo "Hello" && sleep 10'])

    args = shell.parse_args()

    assert args.command == 'echo "Hello" && sleep 10'


# several arguments must keep their boundaries instead of being blindly joined with spaces
def test_parse_args_preserves_argument_boundaries(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['shell.py', '--', 'python', '-c', 'print("hello world")'])

    args = shell.parse_args()

    assert shlex.split(args.command) == ['python', '-c', 'print("hello world")']


@pytest.mark.parametrize(
    ("raised_exception", "expected_status"),
    [
        (subprocess.CalledProcessError(7, ["bash", "-ec", "exit 7"]), 7),
        (subprocess.TimeoutExpired(["bash", "-ec", "sleep 2"], 1), 124),
        (FileNotFoundError("missing-shell"), 127),
        (RuntimeError("runner failed"), 1),
        (ValueError("bad configuration"), 1),
        (KeyboardInterrupt(), 130),
    ],
)
def test_main_returns_nonzero_status_for_failures(
    monkeypatch,
    tmp_path,
    raised_exception,
    expected_status,
):
    class FailingRunner:
        def __init__(self, **_kwargs):
            self._run_id = None
            self._tmp_folder = Path(tmp_path)

        def run(self):
            raise raised_exception

    monkeypatch.setattr(shell, "parse_args", _main_args)
    monkeypatch.setattr(shell, "ShellScenarioRunner", FailingRunner)
    monkeypatch.setattr(shell, "_report_shell_error", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(shell, "DB", type("FakeDB", (), {}))

    assert shell.main() == expected_status


# ScenarioRunner.run() does not remove its temporary folder, so a failing run must not leak it either
def test_main_cleans_tmp_folder_when_the_run_fails(monkeypatch, tmp_path):
    tmp_folder = tmp_path / "gmt-tmp"
    tmp_folder.mkdir()
    (tmp_folder / "leftover").write_text("x", encoding="utf-8")

    class FailingRunner:
        def __init__(self, **_kwargs):
            self._run_id = None
            self._tmp_folder = tmp_folder

        def run(self):
            raise RuntimeError("runner failed")

    monkeypatch.setattr(shell, "parse_args", lambda: _main_args(file_cleanup=True))
    monkeypatch.setattr(shell, "ShellScenarioRunner", FailingRunner)
    monkeypatch.setattr(shell, "_report_shell_error", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(shell, "DB", type("FakeDB", (), {}))

    assert shell.main() == 1
    assert not tmp_folder.exists()


# a broken --config-override must go through the CLI error handling and not blow up with a traceback
def test_main_reports_invalid_config_override_instead_of_raising(monkeypatch):
    reported = []

    monkeypatch.setattr(shell, "parse_args", lambda: _main_args(config_override="/does/not/exist.txt"))
    monkeypatch.setattr(shell, "_report_shell_error", lambda *args, **kwargs: reported.append(kwargs))
    monkeypatch.setattr(shell, "DB", type("FakeDB", (), {}))

    assert shell.main() == 1
    # without a valid config we do not know which DB we would be writing this error to
    assert reported and reported[0]["persist"] is False


# GlobalConfig is a singleton that does nothing when a config is already loaded, so a missing config file
# can only be provoked in a fresh process
@pytest.mark.parametrize("config_override", ["/does/not/exist.yml", "/does/not/exist.txt"])
def test_shell_cli_reports_missing_config_override_without_traceback(config_override):
    ps = subprocess.run(
        ['python3', f'{GMT_DIR}/shell.py', '--config-override', config_override, '--dev-no-save', '--', 'echo 1'],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='UTF-8',
    )

    assert ps.returncode == 1
    # the message only exists on the handled path - an uncaught exception would just dump the traceback
    assert 'Could not load the config override' in ps.stderr
    assert 'MEASUREMENT SUCCESSFULLY COMPLETED' not in ps.stdout


def test_shell_cli_end_to_end():
    ps = subprocess.run(
        ['python3', f'{GMT_DIR}/shell.py',
         '--config-override', f'{GMT_DIR}/tests/test-config.yml',
         '--dev-no-save', '--dev-no-metrics', '--dev-no-phase-stats',
         '--', 'echo shell-e2e-ok'],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='UTF-8',
    )

    assert ps.returncode == 0, ps.stderr
    assert 'will execute directly on the host system' in ps.stdout
    assert 'command on [HOST]' in ps.stdout
    assert 'MEASUREMENT SUCCESSFULLY COMPLETED' in ps.stdout


def test_shell_cli_end_to_end_with_save():
    try:
        ps = subprocess.run(
            ['python3', f'{GMT_DIR}/shell.py',
             '--config-override', f'{GMT_DIR}/tests/test-config.yml',
             '--name', 'shell-e2e-saved',
             '--dev-no-metrics', '--dev-no-phase-stats',
             '--', 'echo shell-e2e-ok'],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='UTF-8',
        )

        assert ps.returncode == 0, ps.stderr
        assert 'MEASUREMENT SUCCESSFULLY COMPLETED' in ps.stdout
        assert '/stats.html?id=' in ps.stdout

        run = DB().fetch_one("SELECT uri, branch, filename FROM runs WHERE name = 'shell-e2e-saved'")
        assert run is not None
        assert run[0] is not None # uri is the working directory the command ran from
        assert run[1] == '[SHELL]'
        assert run[2] == 'shell-command'
    finally:
        Tests.reset_db() # this file opts out of the global DB cleanup fixture, so clean up explicitly
