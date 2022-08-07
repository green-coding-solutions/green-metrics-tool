import pandas as pd
import psycopg2
import argparse
from pathlib import Path
from io import StringIO

parser = argparse.ArgumentParser()
parser.add_argument("filename", type=str)

parser.add_argument("project_id", type=str)
parser.add_argument("db_host", type=str)
parser.add_argument("db_pw", type=str)


args = parser.parse_args()

conn = psycopg2.connect("host=%s user=postgres dbname=green-coding password=%s" % (args.db_host, args.db_pw))

df = pd.read_csv(args.filename)

if df.isna().any().any() :
    print("\nError: Dataframe contains NA columns! Please check the CSV file manually\n")
    exit(2)



df = df.rename({"Unnamed: 0": "time"}, axis=1)


df = df[['time', 'Differential 5 - 6 Last (V)',
    'Differential 7 - 8 Last (V)',
    'Differential 9 - 10 Last (V)',
    'Differential 11 - 12 Last (V)',
    'Differential 13 - 14 Last (V)',
    'Differential 15 - 16 Last (V)',]]

df = df.rename({
    'Differential 5 - 6 Last (V)': 'ch_5',
    'Differential 7 - 8 Last (V)': 'ch_7',
    'Differential 9 - 10 Last (V)': 'ch_9',
    'Differential 11 - 12 Last (V)': 'ch_11',
    'Differential 13 - 14 Last (V)': 'ch_13',
    'Differential 15 - 16 Last (V)': 'ch_15'
    }, axis=1)

# bring timestamp to our used microsecond format
df.time = (df.time * 1000000).astype(int)

# we make this here AFTER the int conversion, cause otherwise we get a bit off floating point values like 0.09999995412
measurement_interval = (df.time[1] - df.time[0])/1000000
print(f"Detected measurement_interval: {measurement_interval} s")


# Divide voltages by resistance to get I.
# Then multiply with constant voltage 12 V to get Power.
# Then multiply with measurement_interval to get Joules
# Then multiply by 10**3 to get millijoules
df.ch_5 = (df.ch_5 / 0.5) * 12 * measurement_interval * 10**3
df.ch_7 = (df.ch_7 / 0.5) * 12 * measurement_interval * 10**3
df.ch_9 = (df.ch_9 / 0.5) * 12 * measurement_interval * 10**3
df.ch_11 = (df.ch_11 / 0.5) * 12 * measurement_interval * 10**3
df.ch_13 = (df.ch_13 / 0.5) * 12 * measurement_interval * 10**3
df.ch_15 = (df.ch_15 / 0.5) * 12 * measurement_interval * 10**3

df = df.astype(int)

df_channel = df.melt(id_vars=['time'], var_name='container_name', value_name='value')

df_channel['project_id'] = args.project_id
df_channel['metric'] = 'atx_energy_channel_system'


f = StringIO(df.to_csv(index=False, header=False))

cur = conn.cursor()
cur.copy_from(f, 'stats', columns=df.columns, sep=',')
conn.commit()
cur.close()

# Manual helpers when setting breakpoint()
# df[(df.time > 1659864742753000) & (df.time < 1659864747853000)].sum().drop('time').sum() # Total Energy in Ws
# (df[(df.time > 1659864742753000) & (df.time < 1659864747853000)].sum().drop('time').sum() / 3600) * 1000 # Total Energy in Ws