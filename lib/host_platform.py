import os
import platform
import shlex
import signal
import subprocess
import tempfile
from pathlib import Path


def system_name():
    return platform.system()

def is_windows():
    return system_name() == 'Windows'


def is_macos():
    return system_name() == 'Darwin'


def is_linux():
    return system_name() == 'Linux'


def get_architecture_name():
    system = system_name().lower()
    if system == 'darwin':
        return 'macos'
    if system == 'windows':
        return 'windows'
    return system


def get_tmp_root():
    if is_windows():
        return Path(tempfile.gettempdir()).resolve(strict=True)
    else:
        return Path('/tmp/').resolve(strict=True)

def clear_file_system_caches():
    if is_windows():
        try:
            subprocess.check_output(
                ['powershell', '-NonInteractive', '-NoProfile', '-Command',
                 'Start-ScheduledTask -TaskName GreenMetricsClearFSCache; '
                 'while ((Get-ScheduledTask -TaskName GreenMetricsClearFSCache).State -eq "Running") { Start-Sleep -Milliseconds 100 }'],
                encoding='UTF-8',
                errors='replace',
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                'Failed to clear filesystem cache on Windows. '
                'Ensure the GreenMetricsClearFSCache scheduled task is registered by re-running install_windows.ps1 as Administrator.'
            ) from e
        return

    subprocess.check_output(['sync'], encoding='UTF-8', errors='replace')

    if is_macos():
        return

    subprocess.check_output(
        ['sudo', Path('/usr/sbin/sysctl').resolve(strict=True).as_posix(), '-w', 'vm.drop_caches=3'],
        encoding='UTF-8',
        errors='replace',
    )


# PowerShell has no argv switches for its strictness settings, they are statements that must run before
# the actual command. We therefore prepend them, separated the same way PowerShell separates statements.
POWERSHELL_STATEMENT_SEPARATOR = '; '


def shell_family(shell):
    # cmd and powershell do not understand the POSIX '-c' convention and also do not express their
    # strictness settings as argv options. Everything else is treated as a POSIX shell.
    # process_helpers.get_shell_options() derives the matching default options from this family.
    shell_binary = Path(shell).name.lower().removesuffix('.exe')
    if shell_binary == 'cmd':
        return 'cmd'
    if shell_binary in ('powershell', 'pwsh'):
        return 'powershell'
    return 'posix'


def shell_command_argv(shell, command, shell_options=()):
    family = shell_family(shell)

    if family == 'cmd':
        # cmd cannot express the strictness the POSIX options express and has no place in its invocation
        # syntax to put them. process_helpers.get_shell_options() therefore returns none for cmd by default.
        # Anything the user configured explicitly would have to be dropped right here, which would make GMT
        # look like it applied them, so we refuse loudly instead.
        if shell_options:
            raise RuntimeError(
                f"`shell-options` were configured for a command that runs in '{shell}', but cmd has no equivalent "
                "for them and they would therefore not be applied at all. Please either remove `shell-options` for "
                "this command, set them to an empty list ('shell-options: []') to state explicitly that no "
                "strictness is wanted, or use a shell that supports them (for instance 'shell: pwsh')."
            )
        return [shell, '/d', '/s', '/c', command]

    if family == 'powershell':
        # For PowerShell the options are statements (see process_helpers.DEFAULT_SHELL_OPTIONS_POWERSHELL),
        # so they are prepended to the command instead of being passed as argv.
        if shell_options:
            command = POWERSHELL_STATEMENT_SEPARATOR.join([*shell_options, command])
        return [shell, '-NoProfile', '-NonInteractive', '-Command', command]

    return [shell, *shell_options, '-c', command]


def join_shell_arguments(parts):
    if is_windows():
        return subprocess.list2cmdline(parts)
    return shlex.join(parts)


def popen_process_group_kwargs():
    if is_windows():
        return {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
    return {'preexec_fn': os.setsid}


def set_nonblocking(pipe):
    if pipe is None or not hasattr(os, 'set_blocking'):
        return
    os.set_blocking(pipe.fileno(), False)


def terminate_process_group(ps, cmd):
    if is_windows():
        print(f"Trying to terminate {cmd} with PID: {ps.pid}")
        try:
            ps.send_signal(signal.CTRL_BREAK_EVENT)
        except (AttributeError, ProcessLookupError, OSError):
            ps.terminate()
        try:
            ps.wait(timeout=10)
        except subprocess.TimeoutExpired as exc:
            ps.kill()
            raise RuntimeError(f"Killed the process {cmd}. This could lead to corrupted data!") from exc
        return

    pgid = os.getpgid(ps.pid)
    print(f"Trying to kill {cmd} with PGID: {pgid}")

    os.killpg(pgid, signal.SIGTERM)
    try:
        ps.wait(timeout=10)
    except subprocess.TimeoutExpired as exc:
        os.killpg(pgid, signal.SIGKILL)
        raise RuntimeError(f"Killed the process {cmd} with SIGKILL. This could lead to corrupted data!") from exc


def docker_host_path(path):
    return Path(path).resolve(strict=True).as_posix()


def split_volume_spec(volume, maxsplit=-1):
    if not is_windows() or len(volume) < 3 or volume[1] != ':' or volume[2] not in ('\\', '/'):
        return volume.split(':', maxsplit)

    protected_drive = volume[:2]
    rest = volume[2:]
    parts = rest.split(':', maxsplit)
    parts[0] = f"{protected_drive}{parts[0]}"
    return parts


def _docker_image_rows():
    ps = subprocess.run(
        ['docker', 'images', '--format', '{{.Repository}}:{{.Tag}}'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        encoding='UTF-8',
        errors='replace',
    )
    if ps.returncode != 0:
        raise subprocess.CalledProcessError(ps.returncode, ps.args, output=ps.stdout, stderr=ps.stderr)

    return ps.stdout.splitlines()


def remove_gmt_tmp_images():
    from lib.utils import get_test_worker_id, is_test_run, GMT_TMP_IMAGE_SUFFIX_RUN, GMT_TMP_IMAGE_SUFFIX_TEST # pylint: disable=import-outside-toplevel
    # local import: lib.utils imports this module (host_platform) at module scope, so importing it
    # back at module scope here would create an import cycle.

    # ScenarioRunner._clean_image_name() suffixes its tags with this worker's pytest-xdist id (when
    # running under -n), precisely so this sweep only ever removes images this worker itself built -
    # matching on the bare suffix here would also catch (and force-remove) images another,
    # concurrently-running worker just built or is still using, since that substring is common to
    # every worker's tags. get_test_worker_id() zero-pads the worker id itself (e.g. 'gw1' ->
    # 'gw001'), so a plain substring match here can't drift onto a different worker's images the
    # way it could with unpadded ids ('gw1' being a prefix of 'gw10'..'gw19').
    #
    # is_test_run() picks between the production and test tag namespaces - see
    # utils.gmt_tmp_image_name(). Without this split, a test run invoked without -n (so
    # get_test_worker_id() is also None) would fall back to the exact same unsuffixed production
    # substring a real production run uses, and this sweep would force-remove that run's images too.
    worker_id = get_test_worker_id()
    base_suffix = GMT_TMP_IMAGE_SUFFIX_TEST if is_test_run() else GMT_TMP_IMAGE_SUFFIX_RUN
    suffix = f'_{base_suffix}_{worker_id}' if worker_id else f'_{base_suffix}'

    image_names = [image_name for image_name in _docker_image_rows() if suffix in image_name]

    if image_names:
        subprocess.run(['docker', 'rmi', '-f', *image_names], stderr=subprocess.DEVNULL, check=False)


def stop_all_docker_containers():
    ps = subprocess.run(
        ['docker', 'ps', '-aq'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        encoding='UTF-8',
        errors='replace',
    )
    if ps.returncode != 0:
        raise subprocess.CalledProcessError(ps.returncode, ps.args, output=ps.stdout, stderr=ps.stderr)

    container_ids = [container_id for container_id in ps.stdout.splitlines() if container_id]
    if container_ids:
        subprocess.run(['docker', 'stop', *container_ids], check=False)


def remove_docker_images_except(whitelist):
    image_names = [
        image_name
        for image_name in _docker_image_rows()
        if not any(whitelisted_image in image_name for whitelisted_image in whitelist)
    ]
    if image_names:
        subprocess.run(['docker', 'rmi', '-f', *image_names], check=False)
