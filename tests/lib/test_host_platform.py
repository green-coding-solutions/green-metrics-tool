from lib import host_platform
from lib.process_helpers import DEFAULT_SHELL_OPTIONS


def test_shell_command_argv_posix_shell():
    assert host_platform.shell_command_argv('bash', 'echo 1') == ['bash', '-c', 'echo 1']
    assert host_platform.shell_command_argv('/bin/sh', 'echo 1') == ['/bin/sh', '-c', 'echo 1']


def test_shell_command_argv_posix_shell_with_options():
    assert host_platform.shell_command_argv('bash', 'echo 1', DEFAULT_SHELL_OPTIONS) == ['bash', *DEFAULT_SHELL_OPTIONS, '-c', 'echo 1']
    assert host_platform.shell_command_argv('/bin/sh', 'echo 1', ['-e']) == ['/bin/sh', '-e', '-c', 'echo 1']


def test_shell_command_argv_cmd():
    assert host_platform.shell_command_argv('cmd', 'echo 1') == ['cmd', '/d', '/s', '/c', 'echo 1']
    assert host_platform.shell_command_argv('cmd.exe', 'echo 1') == ['cmd.exe', '/d', '/s', '/c', 'echo 1']


# cmd and powershell have no equivalent for the POSIX shell options, so they must be dropped and never
# leak into the native invocation syntax
def test_shell_command_argv_windows_shells_ignore_shell_options():
    assert host_platform.shell_command_argv('cmd.exe', 'echo 1', DEFAULT_SHELL_OPTIONS) == ['cmd.exe', '/d', '/s', '/c', 'echo 1']
    assert host_platform.shell_command_argv('pwsh', 'echo 1', DEFAULT_SHELL_OPTIONS) == ['pwsh', '-NoProfile', '-NonInteractive', '-Command', 'echo 1']


def test_shell_command_argv_powershell():
    assert host_platform.shell_command_argv('powershell.exe', 'echo 1') == ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', 'echo 1']
    assert host_platform.shell_command_argv('pwsh', 'echo 1') == ['pwsh', '-NoProfile', '-NonInteractive', '-Command', 'echo 1']
