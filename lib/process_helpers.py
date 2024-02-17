import signal
import os
import subprocess

def kill_pg(ps, cmd):
    pgid = os.getpgid(ps.pid)
    print(f"Trying to kill {cmd} with PGID: {pgid}")

    os.killpg(pgid, signal.SIGTERM)
    try:
        ps.wait(timeout=10)
    except subprocess.TimeoutExpired as exc:
        # If the process hasn't gracefully exited after 5 seconds we kill it
        os.killpg(pgid, signal.SIGKILL)
        raise RuntimeError(f"Killed the process {cmd} with SIGKILL. This could lead to corrupted data!") from exc

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
