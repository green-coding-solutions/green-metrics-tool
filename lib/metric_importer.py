from io import StringIO

from lib.db import DB
from metric_providers.network.connections.tcpdump.system.provider import generate_stats_string

def import_measurements_new(df, metric_name, run_id):

    df['measurement_metric_id'] = None # prepare
    detail_names = df[['detail_name', 'unit']].drop_duplicates()

    for _, row in detail_names.iterrows():
        measurement_metric_id = DB().fetch_one('''
            INSERT INTO measurement_metrics (run_id, metric, detail_name, unit)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        ''', params=(run_id, metric_name, row['detail_name'], row['unit']))[0]
        df.loc[(df['detail_name'] == row['detail_name']) & (df['unit'] == row['unit']), 'measurement_metric_id'] = measurement_metric_id

    f = StringIO(df[['measurement_metric_id', 'value', 'time']]
        .to_csv(index=False, header=False))
    DB().copy_from(file=f, table='measurement_values', columns=['measurement_metric_id', 'value', 'time'], sep=',')
    f.close()

def import_measurements(df, metric_name, run_id, containers=None):

    if metric_name == 'network_connections_proxy_container_dockerproxy':

        df['run_id'] = run_id
        f = StringIO(df.to_csv(index=False, header=False))
        DB().copy_from(file=f, table='network_intercepts', columns=df.columns, sep=',')
        f.close()

    elif metric_name == 'network_connections_tcpdump_system':
        DB().query("""
            UPDATE runs
            SET logs= COALESCE(logs, '') || %s -- append
            WHERE id = %s
            """, params=(generate_stats_string(df), run_id))

    else:

        if 'container_id' in df.columns:
            df = map_container_id_to_detail_name(df, containers)

        df['run_id'] = run_id

        f = StringIO(df.to_csv(index=False, header=False))
        DB().copy_from(file=f, table='measurements', columns=df.columns, sep=',')
        f.close()


def map_container_id_to_detail_name(df, containers=None):
    df['detail_name'] = df.container_id
    for container_id in containers:
        df.loc[df.detail_name == container_id, 'detail_name'] = containers[container_id]['name']
    df = df.drop('container_id', axis=1)

    return df
