import os
import sys
from lib.terminal_colors import TerminalColors

def check_venv():
    if (sys.version_info.major, sys.version_info.minor) < (3, 10):
        print('Python version is NOT greater than or equal to 3.10. GMT requires Python 3.10 at least. Please upgrade your Python version.')
        sys.exit(1)

    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    venv_path = os.path.realpath(os.path.join(CURRENT_DIR, '..', 'venv'))
    if sys.prefix != venv_path:
        print(TerminalColors.FAIL)
        print(f"Error:\n\nYou are not using a venv, or venv is not in expected directory {venv_path}\nCurrent venv is in {sys.prefix}\n\nThe Green Metrics Tool needs a venv to correctly find installed packages and also necessary include paths.\nPlease check the installation instructions on https://docs.green-coding.io/docs/installation/\n\nMaybe you just forgot to activate your venv? Try:\n$ source venv/bin/activate")
        print(TerminalColors.ENDC)
        sys.exit(1)
