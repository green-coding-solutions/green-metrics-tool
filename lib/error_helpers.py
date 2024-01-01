import sys
import traceback

from lib.terminal_colors import TerminalColors
from lib.global_config import GlobalConfig


def end_error(*errors):
    log_error(*errors)
    sys.exit(1)


def format_error(*errors):
    err = ''

    for error in errors:
        err += str(error) + "\n"

    error_string = f"""
        \n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n
         Error: {err}
        \n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n
        {traceback.format_exc()}
        \n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n
    """

    return error_string


def log_error(*errors):
    error_log_file = GlobalConfig().config['machine']['error_log_file']

    err = ''
    for error in errors:
        err += str(error) + "\n"

    if error_log_file:
        try:
            with open(error_log_file, 'a', encoding='utf-8') as file:
                print('\n\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n', file=file)
                print('Error: ', err, file=file)
                print('\n\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n', file=file)
                print(traceback.format_exc(), file=file)
                print('\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n', file=file)
        except (IOError ,FileNotFoundError, PermissionError):
            print(TerminalColors.FAIL, "\nError: Cannot create file in the specified location because file is not found or not writable", TerminalColors.ENDC, file=sys.stderr)

    # For terminal logging we invert the order. It is better readable if the error is at the bottom
    print(TerminalColors.FAIL,
          '\n\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n', file=sys.stderr)
    print(traceback.format_exc(), file=sys.stderr)
    print('\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n', file=sys.stderr)
    print('Error: ', err, file=sys.stderr)
    print('\n\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n',
          TerminalColors.ENDC, file=sys.stderr)
