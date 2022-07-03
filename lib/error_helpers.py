import sys
import traceback
from setup_functions import get_config

def end_error(*errors):
    log_error(*errors)
    exit(2)

def format_error(*errors):
    err = "Error: "

    for e in errors:
        err+= str(e)

    error_string = f"""
        \n\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n
        {err}
        <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        {traceback.format_exc()}
        <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    """

    return error_string

def log_error(*errors):
    print("\n\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n", file=sys.stderr)
    print("Error: ", *errors, file=sys.stderr)
    print("\n\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n", file=sys.stderr)
    print(traceback.format_exc(), file=sys.stderr)
    print("\n\n<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<>>>>>>>>>>>>>>>>>>>>>>>>>>>>>\n\n", file=sys.stderr)
    # TODO: log to file

if __name__ == "__main__":
    import argparse
    import os

    sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../tools')
    from send_email import send_error_email

    
    user_email="dan@green-coding.org"
    p = "87851711-866f-433e-8117-2c54045a90ec"

    email_error("Docker command failed.", "woogabooga", user_email=user_email, project_id=p)