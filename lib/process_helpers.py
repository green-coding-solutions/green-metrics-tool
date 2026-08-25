import shlex
import subprocess

from lib import host_platform

# Options that are set for every command that is run through a shell.
# They make the shell fail on the first error, on unset variables and on errors in a pipe.
# Can be overridden per command with the 'shell-options' key in the usage_scenario.yml
DEFAULT_SHELL_OPTIONS = ('-o', 'errexit', '-o', 'nounset', '-o', 'pipefail')

# Not every shell supports all of the options we set by default (POSIX only mandates errexit and nounset).
# Since we cannot probe every shell before every call we rather run into the error and then give a helpful hint.
SHELL_OPTION_ERROR_MARKERS = ('illegal option', 'invalid option', 'unrecognized option', 'unknown option', 'bad option')

def get_shell_options(cmd_obj):
    shell_options = cmd_obj.get('shell-options', DEFAULT_SHELL_OPTIONS)

    if isinstance(shell_options, str):
        shell_options = shlex.split(shell_options)

    return list(shell_options)

def get_shell_options_error(cmd, stderr):
    # Some shells (busybox ash for instance) even exit with returncode 0 when an option is unknown and then
    # silently do not run the command at all. Therefore we must look at the stderr and not only at the returncode.
    cmd_list = cmd if isinstance(cmd, list) else str(cmd).split()
    option_names = [option_name for flag, option_name in zip(cmd_list, cmd_list[1:]) if flag == '-o']

    if not option_names:
        return ''

    stderr_string = str(stderr).lower()

    if not any(marker in stderr_string for marker in SHELL_OPTION_ERROR_MARKERS):
        return ''

    if not any(option_name.lower() in stderr_string for option_name in option_names):
        return ''

    return (f"The used shell does not support the shell options ({' '.join(option_names)}) that were set for this command. "
            f"Please note that your command was possibly not executed at all!\n"
            f"GMT sets '{' '.join(DEFAULT_SHELL_OPTIONS)}' by default so that errors in your commands cannot go unnoticed.\n"
            "Please either use a shell that supports these options (for instance 'shell: bash') or override them for this "
            "command with the 'shell-options' key in your usage_scenario.yml. An empty list ('shell-options: []') disables "
            "them entirely, but then errors in your command may go unnoticed.")

def kill_pg(ps, cmd):
    host_platform.terminate_process_group(ps, cmd)

def kill_ps(ps, cmd):
    print(f"Trying to kill {cmd} with PID: {ps.pid}")

    ps.terminate()
    try:
        ps.wait(timeout=10)
    except subprocess.TimeoutExpired as exc:
        ps.kill()
        raise RuntimeError(f"Killed the process {cmd} with SIGKILL. This could lead to corrupted data!") from exc


# currently unused
def timeout(process, cmd: str, duration: int):
    try:
        # subprocess.wait tries to use the syscall waitpid() on POSIX.
        # If that fails however it will go into a partial spin-lock on the process (500us sleep loop).
        # This could maybe be optimized with manual code
        # Also if this code is slow on windows it should be reimplemented
        process.wait(duration)
    except subprocess.TimeoutExpired as exc:
        print(f"Process exceeded runtime of {duration}s. Terminating ...")
        process.terminate()
        try:
            process.wait(5)
        except subprocess.TimeoutExpired as exc2:
            print("Process could not terminate in 5s time. Killing ...")
            process.kill()
            raise RuntimeError(f"Process could not terminate in 5s time and was killed: {cmd}") from exc2

        raise RuntimeError(f"Process exceeded runtime of {duration}s: {cmd}") from exc

def check_process_failed(process, detach: False):
    # detach allows processes to fail with 255, which means ctrl+C. This is how we kill processes.
    if (detach is False and process.returncode != 0) or \
        (detach is True and process.returncode is not None and process.returncode != 0 and process.returncode != 255 and process.returncode != -15 and process.returncode != -9):
        # code 9 is SIGKILL in Linux
        # code 15 is SIGTERM in Linux
        # code 255 is Sigtermn in macos
        return True
    return False
