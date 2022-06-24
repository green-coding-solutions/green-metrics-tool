import sys

class Debug:
    active = False

    def __init__(self, a):
        if a is not None:
            self.active = True
        else:
            self.active = False

    def stop(self):
        if self.active is not None or False:
            print("Debug mode is active. Pausing. Please press Enter to continue ...")
            sys.stdin.readline()