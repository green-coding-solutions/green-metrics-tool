import sys
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
    error_file = GlobalConfig().config['error']['file']

    if error_file != 'None':
        with open(error_file, 'w') as file:
            print('\n\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n', file=file)
            print('Error: ', *errors, file=file)
            print('\n\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n', file=file)
            print(traceback.format_exc(), file=file)
            print('\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n', file=file)

    print(TerminalColors.FAIL,
          '\n\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n', file=sys.stderr)
    print('Error: ', *errors, file=sys.stderr)
    print('\n\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n', file=sys.stderr)
    print(traceback.format_exc(), file=sys.stderr)
    print('\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< 0_o >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n',
          TerminalColors.ENDC, file=sys.stderr)
