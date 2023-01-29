#!/usr/bin/env python3
#pylint: disable=invalid-name

from powerspy2 import PowerSpy2

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Print device communication')
    parser.add_argument('--device', default='/dev/rfcomm0', help='RFCOMM device to connect to')
    parser.add_argument('--interval', '-i', type=int, default=1000, help='Measurement interval in number of ms')
    parser.add_argument('--mjoule', '-mj', action='store_true', help='Outputs the value in milli Joule (mJ)')
    parser.add_argument('--unit', '-u', default='mW', help='Specify the unit. [mW, W, mJ, J]')

    args = parser.parse_args()

    p = PowerSpy2(args.device)
    if args.debug:
        p.debug = True

    if args.mjoule:
        args.interval = 1000
        args.unit = "mJ"

    #p.measurePowerRealtime(p.mseconds_to_period(args.interval))
    p.measurePowerRealtime(args.interval, args.unit)
