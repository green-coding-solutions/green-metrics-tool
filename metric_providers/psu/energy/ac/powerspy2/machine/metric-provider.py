#!/usr/bin/env python3

from metric_providers.psu.energy.ac.powerspy2.machine.powerspy2 import PowerSpy2

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Print device communication')
    parser.add_argument('--device', default='/dev/rfcomm0', help='RFCOMM device to connect to')
    parser.add_argument('--interval', '-i', type=int, default=1000, help='Measurement interval in number of ms')
    parser.add_argument('--unit', '-u', default='mW', help='Specify the unit. [mW, W, mJ, J]')

    args = parser.parse_args()

    p = PowerSpy2(args.device)
    if args.debug:
        p.debug = True

    p.measurePowerRealtime(args.interval, args.unit)
