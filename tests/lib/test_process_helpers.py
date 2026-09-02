import pytest

from lib.process_helpers import (
    DEFAULT_SHELL_OPTIONS,
    DEFAULT_SHELL_OPTIONS_POWERSHELL,
    get_shell_options,
)


def test_get_shell_options_defaults_to_posix_options():
    assert get_shell_options({'command': 'echo 1'}) == list(DEFAULT_SHELL_OPTIONS)
    assert get_shell_options({'command': 'echo 1'}, 'bash') == list(DEFAULT_SHELL_OPTIONS)
    assert get_shell_options({'command': 'echo 1'}, '/bin/sh') == list(DEFAULT_SHELL_OPTIONS)


def test_get_shell_options_posix_override():
    assert get_shell_options({'command': 'echo 1', 'shell-options': ['-o', 'errexit']}, 'bash') == ['-o', 'errexit']
    assert get_shell_options({'command': 'echo 1', 'shell-options': '-o errexit -o pipefail'}, 'bash') == ['-o', 'errexit', '-o', 'pipefail']
    assert not get_shell_options({'command': 'echo 1', 'shell-options': []}, 'bash')


# The POSIX '-o' options mean nothing to PowerShell, so the defaults must be derived from the shell
# rather than being handed down and then dropped
def test_get_shell_options_derives_powershell_defaults():
    assert get_shell_options({'command': 'echo 1'}, 'pwsh') == list(DEFAULT_SHELL_OPTIONS_POWERSHELL)
    assert get_shell_options({'command': 'echo 1'}, 'powershell.exe') == list(DEFAULT_SHELL_OPTIONS_POWERSHELL)


def test_get_shell_options_powershell_override_stays_verbatim():
    # a PowerShell statement is not a token list, splitting it would tear it apart at every space
    assert get_shell_options({'command': 'echo 1', 'shell-options': 'Set-StrictMode -Version Latest'}, 'pwsh') == ['Set-StrictMode -Version Latest']
    assert not get_shell_options({'command': 'echo 1', 'shell-options': []}, 'pwsh')


def test_get_shell_options_cmd_has_no_defaults():
    assert not get_shell_options({'command': 'echo 1'}, 'cmd')
    assert not get_shell_options({'command': 'echo 1', 'shell-options': []}, 'cmd.exe')


# cmd cannot express the options at all. Silently ignoring what the user configured would make GMT look
# like it applied them, so this must be an error instead.
def test_get_shell_options_cmd_rejects_explicit_options():
    with pytest.raises(RuntimeError) as exc:
        get_shell_options({'command': 'echo 1', 'shell-options': ['-o', 'errexit']}, 'cmd.exe')

    assert 'cmd has no equivalent' in str(exc.value)
