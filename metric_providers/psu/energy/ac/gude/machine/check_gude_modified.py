#!/usr/bin/env python3

import json
import time
import sys
import requests


def main(sampling_rate):
    url = 'http://192.168.178.32/status.json'

    only_values = 0x4000
    cgi = {'components': only_values}  # simple-sensors + and only values

    sampling_rate = float(sampling_rate)

    target_sleep_time = sampling_rate / 1000.0

    while True:  # loop until CTRL+C
        timestamp_before = time.time_ns()
        time.sleep(target_sleep_time)

        data = json.loads(requests.get(url, params=cgi, verify=False, auth=None, timeout=15).text)

        # print(data) # DEBUG
        timestamp_after = time.time_ns()
        effective_sleep_time_ns = timestamp_after - timestamp_before
        # print(effective_sleep_time_ns / 1_000_000_000) # DEBUG
        # we want microjoule. Therefore / 10**6 to get to micro-seconds
        conversion_factor = effective_sleep_time_ns / 1_000
        print(int(timestamp_after / 1_000), int(data['sensor_values']
              [0]['values'][0][4]['v'] * conversion_factor), flush=True)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', type=str, help='Resolution')

    args = parser.parse_args()

    if args.i is None:
        parser.print_help()
        print('Please supply -i to set sampling_rate in milliseconds')
        sys.exit(1)

    main(args.i)
