import signal
import os
import subprocess

def kill_ps(ps_to_kill):
    print('Killing processes')
    for ps_info in ps_to_kill:
        pid = ps_info['ps'].pid
        print(f"Trying to kill {ps_info['cmd']} with PID: {pid}")
        try:
            if ps_info['ps_group'] is True:
                try:
                    ps_group_id = os.getpgid(pid)
                    print(f" with process group {ps_group_id}")
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                    try:
                        ps_info['ps'].wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        # If the process hasn't gracefully exited after 5 seconds we kill it
                        os.killpg(os.getpgid(pid), signal.SIGKILL)
                except ProcessLookupError:
                    # process may be not have been in a process group
                    print(f"Could not find process-group for {pid}")
            # always, just in case the calling process (typically the shell) did not die
            os.kill(pid, signal.SIGTERM)
            try:
                ps_info['ps'].wait(timeout=5)
            except subprocess.TimeoutExpired:
                # If the process hasn't gracefully exited after 5 seconds we kill it
                os.kill(pid, signal.SIGKILL)

        except ProcessLookupError:
            # process may already have ended or been killed in the process group
            print(f"Could not find process {pid}")

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
            #pylint: disable=raise-missing-from
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
