import sys
import os
import traceback
from terminal_colors import TerminalColors
from global_config import GlobalConfig


def end_error(*errors):
    log_error(*errors)
    sys.exit(1)


def format_error(*errors):
    err = 'Error: '

    for error in errors:
        err += str(error)

    error_string = f"""
        \n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n
        {err}
        \n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n
        {traceback.format_exc()}
        \n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n
    """

    return error_string


def log_error(*errors):
    error_log_file = GlobalConfig().config['machine']['error_log_file']

    if error_log_file != 'None':
        if os.access(os.path.dirname(error_log_file), os.W_OK):
            if (os.path.isfile(error_log_file) and os.access(error_log_file, os.W_OK)) or not os.path.isfile(error_log_file):
                try:
                    with open(error_log_file, 'w') as file:
                        print('\n\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n', file=file)
                        print('Error: ', *errors, file=file)
                        print('\n\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n', file=file)
                        print(traceback.format_exc(), file=file)
                        print('\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n', file=file)
                except IOError:
                    print("Cannot create file in the specified location.", file=sys.stderr)

    print(TerminalColors.FAIL,
          '\n\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n', file=sys.stderr)
    print('Error: ', *errors, file=sys.stderr)
    print('\n\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n', file=sys.stderr)
    print(traceback.format_exc(), file=sys.stderr)
    print('\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n',
          TerminalColors.ENDC, file=sys.stderr)
