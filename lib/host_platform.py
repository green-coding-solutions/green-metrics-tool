import os
import platform
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


def get_architecture_name():
    system = system_name().lower()
    if system == 'darwin':
        return 'macos'
    if system == 'windows':
        return 'windows'
    return system


def get_tmp_root():
    return Path(tempfile.gettempdir()).resolve(strict=True)


def clear_file_system_caches():
    if is_windows():
        print('Skipping filesystem cache clearing on Windows')
        return

    subprocess.check_output(['sync'], encoding='UTF-8', errors='replace')

    if is_macos():
        return

    subprocess.check_output(
        ['sudo', Path('/usr/sbin/sysctl').resolve(strict=True).as_posix(), '-w', 'vm.drop_caches=3'],
        encoding='UTF-8',
        errors='replace',
    )


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
        ['docker', 'images', '--format', '{{.Repository}}:{{.Tag}} {{.ID}}'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        encoding='UTF-8',
        errors='replace',
    )
    if ps.returncode != 0:
        raise subprocess.CalledProcessError(ps.returncode, ps.args, output=ps.stdout, stderr=ps.stderr)

    rows = []
    for line in ps.stdout.splitlines():
        parts = line.rsplit(maxsplit=1)
        if len(parts) == 2:
            rows.append((parts[0], parts[1]))
    return rows


def remove_gmt_tmp_images():
    try:
        image_rows = _docker_image_rows()
    except subprocess.CalledProcessError:
        return

    image_ids = [image_id for image_name, image_id in image_rows if 'gmt_run_tmp' in image_name]
    if image_ids:
        subprocess.run(['docker', 'rmi', '-f', *image_ids], stderr=subprocess.DEVNULL, check=False)


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
    image_ids = [
        image_id
        for image_name, image_id in _docker_image_rows()
        if not any(whitelisted_image in image_name for whitelisted_image in whitelist)
    ]
    if image_ids:
        subprocess.run(['docker', 'rmi', '-f', *image_ids], check=False)
