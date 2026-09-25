from io import StringIO

from lib.db import DB
from metric_providers.network.connections.tcpdump.system.provider import generate_stats_string


def import_measurements(df, metric_name, run_id):

    if metric_name == 'network_connections_proxy_container_dockerproxy':

        df['run_id'] = run_id
        f = StringIO(df.to_csv(index=False, header=False))
        DB().copy_from(file=f, table='network_connections_proxy', columns=df.columns, sep=',')
        f.close()

    elif metric_name in ('network_connections_tcpdump_system', 'network_connections_tcpdump_container'):
        # system provider: df is a flat {ip: stats} dict for the whole run -> single '[SYSTEM]' group
        # container provider: df is {container_name: {ip: stats}} -> one group per container
        groups = df if metric_name == 'network_connections_tcpdump_container' else {'[SYSTEM]': df}

        for detail_name, ip_stats in groups.items():
            stats_string = generate_stats_string(ip_stats)
            DB().query(
                "INSERT INTO network_connections_tcpdump (run_id, detail_name, metric, stats) VALUES (%s, %s, %s, %s)",
                params=(run_id, detail_name, metric_name, stats_string),
            )

    else:

        df['run_id'] = run_id

        metric_and_detail_names = df[['metric', 'detail_name', 'unit']].drop_duplicates()

        for _, row in metric_and_detail_names.iterrows():
            measurement_metric_id = DB().fetch_one('''
                INSERT INTO measurement_metrics (run_id, metric, detail_name, unit)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            ''', params=(run_id, row['metric'], row['detail_name'], row['unit']))[0] # using row['metric'] here instead of metric_name, as some providers have multiple metrics inlined like powermetrics
            df.loc[(df['metric'] == row['metric']) & (df['detail_name'] == row['detail_name']) & (df['unit'] == row['unit']), 'measurement_metric_id'] = measurement_metric_id

        df['measurement_metric_id'] = df.measurement_metric_id.astype('int64')

        f = StringIO(df[['measurement_metric_id', 'value', 'time']]
            .to_csv(index=False, header=False))

        DB().copy_from(file=f, table='measurement_values', columns=['measurement_metric_id', 'value', 'time'], sep=',')

        f.close()
