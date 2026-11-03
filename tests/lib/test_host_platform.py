import shlex
import subprocess

import pytest

from lib import host_platform
from lib.process_helpers import DEFAULT_SHELL_OPTIONS, DEFAULT_SHELL_OPTIONS_POWERSHELL


def test_shell_command_argv_posix_shell():
    assert host_platform.shell_command_argv('bash', 'echo 1') == ['bash', '-c', 'echo 1']
    assert host_platform.shell_command_argv('/bin/sh', 'echo 1') == ['/bin/sh', '-c', 'echo 1']


def test_shell_command_argv_posix_shell_with_options():
    assert host_platform.shell_command_argv('bash', 'echo 1', DEFAULT_SHELL_OPTIONS) == ['bash', *DEFAULT_SHELL_OPTIONS, '-c', 'echo 1']
    assert host_platform.shell_command_argv('/bin/sh', 'echo 1', ['-e']) == ['/bin/sh', '-e', '-c', 'echo 1']


def test_shell_command_argv_cmd():
    assert host_platform.shell_command_argv('cmd', 'echo 1') == ['cmd', '/d', '/s', '/c', 'echo 1']
    assert host_platform.shell_command_argv('cmd.exe', 'echo 1') == ['cmd.exe', '/d', '/s', '/c', 'echo 1']


# cmd has no equivalent for the shell options and no place in its invocation syntax to put them. Dropping
# them here would make GMT look like it applied them, so applying non-empty options must be an error.
def test_shell_command_argv_cmd_rejects_shell_options():
    with pytest.raises(RuntimeError) as exc:
        host_platform.shell_command_argv('cmd.exe', 'echo 1', DEFAULT_SHELL_OPTIONS)

    assert 'cmd has no equivalent' in str(exc.value)


def test_shell_command_argv_cmd_accepts_empty_shell_options():
    assert host_platform.shell_command_argv('cmd.exe', 'echo 1', []) == ['cmd.exe', '/d', '/s', '/c', 'echo 1']


def test_shell_command_argv_powershell():
    assert host_platform.shell_command_argv('powershell.exe', 'echo 1') == ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', 'echo 1']
    assert host_platform.shell_command_argv('pwsh', 'echo 1') == ['pwsh', '-NoProfile', '-NonInteractive', '-Command', 'echo 1']


# PowerShell expresses its shell options as statements, so they are prepended to the command instead of
# being silently discarded
def test_shell_command_argv_powershell_prepends_shell_options_as_statements():
    assert host_platform.shell_command_argv('pwsh', 'echo 1', DEFAULT_SHELL_OPTIONS_POWERSHELL) == [
        'pwsh', '-NoProfile', '-NonInteractive', '-Command',
        "$ErrorActionPreference = 'Stop'; Set-StrictMode -Version Latest; echo 1",
    ]
    assert host_platform.shell_command_argv('powershell.exe', 'echo 1', ["$ErrorActionPreference = 'Stop'"]) == [
        'powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
        "$ErrorActionPreference = 'Stop'; echo 1",
    ]


def test_shell_command_argv_powershell_without_shell_options_leaves_command_untouched():
    assert host_platform.shell_command_argv('pwsh', 'echo 1', []) == ['pwsh', '-NoProfile', '-NonInteractive', '-Command', 'echo 1']


# the shell is resolved with the path flavour of the platform it will run on, so only paths that are
# native to the test platform are asserted here
def test_shell_family():
    assert host_platform.shell_family('bash') == 'posix'
    assert host_platform.shell_family('/bin/sh') == 'posix'
    assert host_platform.shell_family('/usr/local/bin/zsh') == 'posix'
    assert host_platform.shell_family('cmd') == 'cmd'
    assert host_platform.shell_family('cmd.exe') == 'cmd'
    assert host_platform.shell_family('CMD.EXE') == 'cmd'
    assert host_platform.shell_family('powershell.exe') == 'powershell'
    assert host_platform.shell_family('pwsh') == 'powershell'
    assert host_platform.shell_family('PWSH') == 'powershell'


# argument boundaries must survive the reassembly into a single command string
def test_join_shell_arguments_keeps_argument_boundaries():
    joined = host_platform.join_shell_arguments(['python', '-c', 'print("hello world")'])

    assert shlex.split(joined) == ['python', '-c', 'print("hello world")']
    assert joined != 'python -c print("hello world")'


def test_join_shell_arguments_leaves_simple_arguments_readable():
    assert host_platform.join_shell_arguments(['sleep', '5']) == 'sleep 5'


# Images pulled by digest have no tag. They must be addressed as repo@digest, because `repo:<none>`
# is an invalid reference that `docker rmi` rejects - which made --full-docker-prune silently keep them.
def test_parse_docker_image_references():
    output = (
        'martizih/kaniko\tslim\tsha256:aaa\n'
        'mariadb\t<none>\tsha256:dd9b303aed4f\n'
        'postgres\t16\t<none>\n'
        '<none>\t<none>\t<none>\n'
        'ribalba/benchbase\t<none>\tsha256:85c175561d83\n'
        'ribalba/benchbase\t<none>\tsha256:f7a0f21e8bfc\n'
        '\n'
    )

    assert host_platform._parse_docker_image_references(output) == [ # pylint: disable=protected-access
        'martizih/kaniko:slim',
        'mariadb@sha256:dd9b303aed4f',
        'postgres:16',
        'ribalba/benchbase@sha256:85c175561d83',
        'ribalba/benchbase@sha256:f7a0f21e8bfc',
    ]


def test_remove_docker_images_except_removes_digest_pulled_images(monkeypatch):
    calls = []

    def fake_run(args, **_kwargs):
        calls.append(args)
        stdout = 'martizih/kaniko\tslim\tsha256:aaa\nmariadb\t<none>\tsha256:dd9b\npostgres\t16\tsha256:bbb\n'
        return subprocess.CompletedProcess(args, 0, stdout=stdout if args[:2] == ['docker', 'images'] else '', stderr='')

    monkeypatch.setattr(host_platform.subprocess, 'run', fake_run)

    host_platform.remove_docker_images_except(['martizih/kaniko:slim'])

    assert calls[0][:3] == ['docker', 'images', '--digests']
    assert calls[1] == ['docker', 'rmi', '-f', 'mariadb@sha256:dd9b', 'postgres:16']
