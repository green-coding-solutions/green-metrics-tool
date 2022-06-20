from setup_functions import get_config
import traceback
from send_email import send_error_email

def end_error(*errors):
    log_error(*errors)
    exit(2)

def email_error(*errors, email_admin=True, user_email=None, project_id=None):
    config = get_config()
    err = "Error: "

    for e in errors:
        err+= str(e)

    if email_admin:
        send_error_email(config, config['admin']['email'], err, project_id)
    if user_email is not None:
        send_error_email(config, user_email, err, project_id)

def log_error(*errors):
    err = "Error: "
    print("Error: ", *errors)
    # TODO: log to file

if __name__ == "__main__":
    import argparse
    import yaml
    import os
    import sys

    sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../tools')
    from setup_functions import get_config, get_db_connection
    from send_email import send_error_email

    
    user_email="dan@green-coding.org"
    p = "87851711-866f-433e-8117-2c54045a90ec"

    email_error("Docker command failed.", "woogabooga", user_email=user_email, project_id=p)