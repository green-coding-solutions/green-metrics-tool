#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import optimization_providers.base
from lib.terminal_colors import TerminalColors

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('run_id', help='Please supply a run_id')

    args = parser.parse_args()  # script will exit if arguments not present

    print(TerminalColors.HEADER, '\nImporting optimization reporters ...', TerminalColors.ENDC)
    optimization_providers.base.import_reporters()

    print(TerminalColors.HEADER, '\nRunning optimization reporters ...', TerminalColors.ENDC)

    optimization_providers.base.run_reporters(args.run_id, '/tmp/green-metrics-tool')
