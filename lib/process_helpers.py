def kill_pids(ps_to_kill):
    import signal
    import os
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


def timeout(ps, cmd, duration):
    import subprocess
    try:
        ps.wait(duration)
    except subprocess.TimeoutExpired as e:
        print("Process exceeded runtime of 60s. Terminating ...")
        ps.terminate()
        raise RuntimeError(f"Process exceeded runtime of 60s: {cmd}")
        try:
            ps.wait(5)
        except subprocess.TimeoutExpired as e:
            print("Process could not terminate in 5s time. Killing ...")
            ps.kill()
            raise RuntimeError(f"Process could not terminate in 5s time and was killed: {cmd}")


def parse_stream(ps, cmd):
    stderr_stream = ps.stderr.read()
    if stderr_stream != '' :
        raise RuntimeError(f"Stderr of docker exec command '{cmd}' was not empty: {stderr_stream}")

    stdout_stream = ps.stdout.read()
    print(f"stdout of docker exec command '{cmd}' was : {stdout_stream}")
