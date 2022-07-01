import sys

class DebugHelper:

    def __init__(self, a):
        if a is True:
            self.active = True
        else:
            self.active = False

    def pause(self):
        if self.active:
            print("Debug mode is active. Pausing. Please press Enter to continue ...")
            sys.stdin.readline()
