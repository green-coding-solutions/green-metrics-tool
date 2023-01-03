#!/usr/bin/env python3
#pylint: disable=invalid-name

from powerspy2 import PowerSpy2

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Print device communication')
    parser.add_argument('--device', default='/dev/rfcomm0', help='RFCOMM device to connect to')
    parser.add_argument('--interval', '-i', type=int, default=1000, help='Measurement interval in number of ms')

    args = parser.parse_args()

    p = PowerSpy2(args.device)
    if args.debug:
        p.debug = True

    # PowerSpy v2 (assuming all other versions) supports 65535 averaging periods.
    max_avg_period = 65535
    frequency = p.getFrequency()
    periods_seconds = 1382400.0 / frequency

    avg_period = int(round(periods_seconds * (args.interval / 1000)))
    if avg_period > max_avg_period:
        print('PowerSpy capacity exceeded: it will be average of averaged values for one second.')
        avg_period = int(round(periods_seconds))

    p.measurePowerRealtime(avg_period)
