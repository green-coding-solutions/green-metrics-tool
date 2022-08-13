import sys
from terminal_colors import TerminalColors

class DebugHelper:

    def __init__(self, a):
        if a is True:
            self.active = True
        else:
            self.active = False

    def pause(self, msg=""):
        print(TerminalColors.OKCYAN, "\n#############################DEBUG_MODE########################")
        print(msg)
        print("Debug mode is active. Pausing. Please press Enter to continue ...", TerminalColors.ENDC)
        sys.stdin.readline()
