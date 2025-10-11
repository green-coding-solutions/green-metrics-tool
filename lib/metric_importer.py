import json
from io import StringIO

from lib.db import DB
from lib.log_types import LogType
from metric_providers.network.connections.tcpdump.system.provider import generate_stats_string


def import_measurements(df, metric_name, run_id):

    if metric_name == 'network_connections_proxy_container_dockerproxy':

        df['run_id'] = run_id
        f = StringIO(df.to_csv(index=False, header=False))
        DB().copy_from(file=f, table='network_intercepts', columns=df.columns, sep=',')
        f.close()

    elif metric_name == 'network_connections_tcpdump_system':
        stats_string = generate_stats_string(df)

        log_entry = {
            '[SYSTEM]': [{
                'type': LogType.NETWORK_STATS.value,
                'id': str(id(stats_string)),
                'cmd': None,
                'phase': '[MULTIPLE]',
                'stdout': stats_string
            }]
        }

        DB().query("""
            UPDATE runs
            SET logs = COALESCE(logs, '{}'::jsonb) || %s::jsonb
            WHERE id = %s
            """, params=(json.dumps(log_entry), run_id))

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
