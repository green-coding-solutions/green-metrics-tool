import signal
import os
import subprocess

def kill_pids(ps_to_kill):
    print("Killing processes")
    for ps in ps_to_kill:
        print(f"Trying to kill {ps['cmd']} with PID: {ps['pid']}")
        try:
            if(ps['ps_group'] == True):
                try:
                    ps_group_id = os.getpgid(ps['pid'])
                    print(f" with process group {ps_group_id}")
                    os.killpg(os.getpgid(ps['pid']), signal.SIGTERM)
                except ProcessLookupError:
                    print(f"Could not find process-group for {ps['pid']}") # process may be not have been in a process group
            os.kill(ps['pid'], signal.SIGTERM) # always, just in case the calling process (typically the shell) did not die
        except ProcessLookupError:
            print(f"Could not find process {ps['pid']}") # process may already have ended or been killed in the process group


def timeout(ps, cmd: str, duration: int):
    try:
        # subprocess.wait tries to use the syscall waitpid() on POSIX.
        # If that fails however it will go into a partial spin-lock on the process (500us sleep loop).
        # This could maybe be optimized with manual code
        # Also if this code is slow on windows it should be reimplemented
        ps.wait(duration)
    except subprocess.TimeoutExpired as e:
        print(f"Process exceeded runtime of {duration}s. Terminating ...")
        ps.terminate()
        raise RuntimeError(f"Process exceeded runtime of {duration}s: {cmd}")
        try:
            ps.wait(5)
        except subprocess.TimeoutExpired as e:
            print("Process could not terminate in 5s time. Killing ...")
            ps.kill()
            raise RuntimeError(f"Process could not terminate in 5s time and was killed: {cmd}")


def parse_stream_generator(ps, cmd):
    stderr_stream = ps.stderr.read()
    if stderr_stream != '' :
        raise RuntimeError(f"Stderr of docker exec command '{cmd}' was not empty: {stderr_stream}")

    while (pair := ps.stdout.readline()):
        yield pair
