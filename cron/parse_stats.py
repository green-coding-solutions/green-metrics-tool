
def import_stats(project_id, filename):
    import pandas as pd

    from io import StringIO

    with open(filename, 'r') as f:
        csv_data = f.read().replace("\x1b[2J\x1b[H", "")

    df = pd.read_csv(StringIO(csv_data), sep=";", names=["name", "cpu", "mem", "netio"])
    df.loc[df[df['cpu'] == '--'].index] = None # do not remove measurement errors for now
    df['cpu'] = df['cpu'].str.replace('%', '').replace('.', '')

    df = df.join(df['mem'].str.split(' / ', expand=True))
    df = df.rename({0: 'mem_cur', 1: 'mem_max'}, axis="columns")
    df.drop('mem', axis="columns", inplace=True)

    df = df.join(df['netio'].str.split(' / ', expand=True))
    df = df.rename({0: 'net_in', 1: 'net_out'}, axis="columns")
    df.drop('netio', axis="columns", inplace=True)

    # Now we normalize all columns
    def convert_values(el):
        if el == None:
            return None
        elif 'MiB' in el or 'MB' in el:
            return float(el.replace('MiB' ,'').replace('MB' ,''))*100
        elif 'GiB' in el or 'GB' in el:
            return float(el.replace('GiB' ,'').replace('GB' ,''))*100000
        elif 'KiB' in el or 'KB' in el or 'kB' in el:
            return float(el.replace('KiB' ,'').replace('KB' ,'').replace('kB' ,''))/10
        else:
            raise Exception("Could not convert value: ", el)

    for container_name in df['name'].unique():
        df.loc[df.name == container_name, 'seconds'] = range(0,df.loc[df.name == container_name].shape[0])

    import yaml
    import os
    with open("{path}/../config.yml".format(path=os.path.dirname(os.path.realpath(__file__)))) as config_file:
        config = yaml.load(config_file,yaml.FullLoader)

    import psycopg2
    conn = psycopg2.connect("user=%s dbname=%s password=%s" % (config['postgresql']['user'], config['postgresql']['dbname'], config['postgresql']['password']))

    cur = conn.cursor()
    import numpy as np

    for i, row in df.iterrows():
        if(row['cpu'] is None):
                cpu = None
        else:
            cpu = float(row['cpu'])*100
        converted_row = row[['mem_cur', 'mem_max', 'net_in', 'net_out']].apply(convert_values)

        print((project_id, row['name'], cpu, converted_row['mem_cur'], converted_row['mem_max'], converted_row['net_in'], converted_row['net_out'], row['seconds']))
        cur.execute("""
                INSERT INTO stats
                ("project_id", "container_name", "cpu", "mem", "mem_max", "net_in", "net_out", "time")
                VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (project_id, row['name'], cpu, converted_row['mem_cur'], converted_row['mem_max'], converted_row['net_in'], converted_row['net_out'], row['seconds'])
        )
        conn.commit()
    cur.close()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("stats_file", help="Please specify filename where to find the docker stats file. Usually /tmp/docker_stats.log")
    parser.add_argument("project_id", help="Please supply a project_id to attribute the stats to")

    args = parser.parse_args() # script will exit if url is not present

    import_stats(args.project_id, args.stats_file)


