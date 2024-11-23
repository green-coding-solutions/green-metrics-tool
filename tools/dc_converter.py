#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import argparse
from io import StringIO

import psycopg
import pandas as pd

def main(args):
    conn = psycopg.connect(f"host={args.db_host} user=postgres dbname=green-coding password={args.db_pw}")

    df = pd.read_csv(args.filename)

    if df.isna().any().any():
        print('\nError: Dataframe contains NA columns! Please check the CSV file manually\n')
        sys.exit(1)

    df = df.rename({'Unnamed: 0': 'time'}, axis=1)

    df = df.rename({
        'Differential 1 - 2 Ave. (mV)': 'ch_1_12V',
        'Differential 3 - 4 Ave. (mV)': 'ch_3_12V',
        'Differential 5 - 6 Ave. (mV)': 'ch_5_12V',
        'Differential 7 - 8 Ave. (mV)': 'ch_7_12V',
        'Differential 9 - 10 Ave. (mV)': 'ch_9_12V',
        'Differential 11 - 12 Ave. (mV)': 'ch_11_12V',
        #        'Differential 13 - 14 Ave. (mV)': 'ch_13_12V',
        #        'Differential 15 - 16 Ave. (mV)': 'ch_15_12V',
    }, axis=1)

    # bring timestamp to our used microsecond format
    df.time = (df.time * 1000000).astype(int)

    # we make this here AFTER the int conversion, cause otherwise we get a bit off floating point values like 0.09999995412
    measurement_interval = (df.time[1] - df.time[0])/1000000
    print(f"Detected measurement_interval: {measurement_interval} s")

    # Divide millivolts by 1000 to get V.
    # Divide voltages by resistance to get I.
    # Then multiply with constant voltage 12 V to get Power.
    # Then multiply with measurement_interval to get Joules
    # Then multiply by 10**3 to get millijoules
    df.ch_1_12V = ((df.ch_1_12V / 1000) / 0.005) * \
        12 * measurement_interval * 10**3
    df.ch_3_12V = ((df.ch_3_12V / 1000) / 0.005) * \
        12 * measurement_interval * 10**3
    df.ch_5_12V = ((df.ch_5_12V / 1000) / 0.005) * \
        12 * measurement_interval * 10**3
    df.ch_7_12V = ((df.ch_7_12V / 1000) / 0.005) * \
        12 * measurement_interval * 10**3
    df.ch_9_12V = ((df.ch_9_12V / 1000) / 0.005) * \
        12 * measurement_interval * 10**3
    df.ch_11_12V = ((df.ch_11_12V / 1000) / 0.005) * \
        12 * measurement_interval * 10**3
#    df.ch_13_12V = ((df.ch_13_12V / 1000) / 0.005) * 12 * measurement_interval * 10**3
#    df.ch_15_12V = ((df.ch_15_12V / 1000) / 0.005) * 12 * measurement_interval * 10**3

    df = df.astype(int)

    df = df.melt(id_vars=['time'], var_name='detail_name', value_name='value')

    df['run_id'] = args.run_id
    df['metric'] = 'atx_energy_dc_channel'

    f = StringIO(df.to_csv(index=False, header=False))

    cur = conn.cursor()
    cur.copy_from(f, 'stats', columns=df.columns, sep=',')
    conn.commit()
    cur.close()

    # Manual helpers when setting breakpoint()
    # df[(df.time > 1659864742753000) & (df.time < 1659864747853000)].sum().drop('time').sum() # Total Energy in Ws
    # (df[(df.time > 1659864742753000) & (df.time < 1659864747853000)].sum().drop('time').sum() / 3600) * 1000 # Total Energy in Ws


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('filename', type=str)

    parser.add_argument('run_id', type=str)
    parser.add_argument('db_host', type=str)
    parser.add_argument('db_pw', type=str)

    main(parser.parse_args())
