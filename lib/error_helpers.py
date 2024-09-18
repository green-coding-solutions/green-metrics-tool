import sys
import traceback

from lib.terminal_colors import TerminalColors
from lib.global_config import GlobalConfig
from lib.job.base import Job

def end_error(*messages, **kwargs):
    log_error(*messages, **kwargs)
    sys.exit(1)


def format_error(*messages, **kwargs):
    err = '\n'.join(messages)
    err += '\n\n'
    err += '\n'.join([f"{key.capitalize()} ({value.__class__.__name__}): {value}" for key, value in kwargs.items()])
    if 'run_id' in kwargs and kwargs['run_id']:
        err += f"\nRun-ID Link: {GlobalConfig().config['cluster']['metrics_url']}/stats.html?id={kwargs['run_id']}"

    error_string = f"""
\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n
{traceback.format_exc()}
\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n
Error: {err}
\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n
    """

    return error_string


def log_error(*messages, **kwargs):
    err = format_error(*messages, **kwargs)

    if error_file := GlobalConfig().config['admin']['error_file']:
        try:
            with open(error_file, 'a', encoding='utf-8') as file:
                print(err, file=file)
        except (IOError ,FileNotFoundError, PermissionError):
            print(TerminalColors.FAIL, "\nError: Cannot create file in the specified location because file is not found or not writable", TerminalColors.ENDC, file=sys.stderr)

    print(TerminalColors.FAIL, err, TerminalColors.ENDC, file=sys.stderr)

    if error_email := GlobalConfig().config['admin']['error_email']:
        Job.insert('email', user_id=None, email=error_email, name='Green Metrics Tool Error', message=err)
