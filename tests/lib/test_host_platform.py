from lib import host_platform


def test_shell_command_argv_posix_shell():
    assert host_platform.shell_command_argv('bash', 'echo 1') == ['bash', '-ec', 'echo 1']
    assert host_platform.shell_command_argv('/bin/sh', 'echo 1') == ['/bin/sh', '-ec', 'echo 1']


def test_shell_command_argv_cmd():
    assert host_platform.shell_command_argv('cmd', 'echo 1') == ['cmd', '/d', '/s', '/c', 'echo 1']
    assert host_platform.shell_command_argv('cmd.exe', 'echo 1') == ['cmd.exe', '/d', '/s', '/c', 'echo 1']


def test_shell_command_argv_powershell():
    assert host_platform.shell_command_argv('powershell.exe', 'echo 1') == ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', 'echo 1']
    assert host_platform.shell_command_argv('pwsh', 'echo 1') == ['pwsh', '-NoProfile', '-NonInteractive', '-Command', 'echo 1']
