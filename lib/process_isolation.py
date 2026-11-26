import signal
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

from lib.global_config import GlobalConfig

# Runs a function in a fresh, short-lived child process and returns its result or re-raises its exception
# in the parent.
#
# Why: A long-running Python process (like cron/client.py) never fully hands memory back to the OS. Modules
# imported once stay imported (e.g. scipy / FastAPI pulled in by the optimization providers) and freed
# libpq result buffers from big queries (phase_stats fetches all measurement values of a run) stay in the
# glibc heap. All of this memory is accounted to the GMT cgroup and thus shows up as "GMT Overhead" in every
# following measurement. When the work happens in a child process the OS reclaims everything once it exits.
#
# Transport of results / exceptions (incl. the remote traceback as __cause__) and crash detection
# (BrokenProcessPool) are handled by ProcessPoolExecutor. Exceptions must be picklable to reach the parent.
#
# We use 'spawn' and not 'fork' as the parent holds a threaded psycopg connection pool which must not be
# duplicated into the child, and because a fork would inherit the already bloated memory of the parent.
#
# Signals: systemd (KillMode=control-group, the default) and Ctrl+C deliver the signal to the child as well.
# The parent does not forward signals, so if only the parent is signalled it waits for the child to finish.

class IsolatedProcessTerminated(Exception):
    pass

_signal_received = False

def _handle_signal(signum, frame): # pylint: disable=unused-argument
    # A spawned child has no Python SIGTERM handler and would be killed instantly, skipping all cleanup
    # (stopping containers, setting the job state etc.). We raise instead, but only on the first signal so that
    # follow-up signals do not interrupt the cleanup that the first exception triggered.
    global _signal_received # pylint: disable=global-statement
    if _signal_received:
        print(f"Isolated process received signal {signum} again. Ignoring as shutdown is already in progress ...")
        return
    _signal_received = True

    if signum == signal.SIGINT:
        raise KeyboardInterrupt('SIGINT received in isolated process')
    raise IsolatedProcessTerminated(f"Signal {signum} received in isolated process")

def _init_child(config_location):
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # The parent might have been started with a --config-override. The child is a fresh interpreter and would
    # otherwise silently fall back to the default config.yml
    GlobalConfig().override_config(config_location=config_location)

def _call(func, args, kwargs):
    try:
        return func(*args, **kwargs)
    finally:
        # multiprocessing workers exit via os._exit(), so atexit hooks do not run. Close the connections cleanly.
        from lib.db import DB # pylint: disable=import-outside-toplevel
        DB.shutdown_if_initialized()

def run_isolated(func, *args, **kwargs):
    with ProcessPoolExecutor(
        max_workers=1,
        mp_context=multiprocessing.get_context('spawn'),
        initializer=_init_child,
        initargs=(GlobalConfig().config_location, ),
    ) as executor:
        return executor.submit(_call, func, args, kwargs).result()
