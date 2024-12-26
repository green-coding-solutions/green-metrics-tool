from io import StringIO

from lib.db import DB

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

def import_measurements(df):
    df = add_effective_resolution_and_jitter(df) # works already on the reference. return just for clarity

    f = StringIO(df.to_csv(index=False, header=False))
    DB().copy_from(file=f, table='measurements', columns=df.columns, sep=',')


# This method could also be placed in the metric_providers/base.py
# However, since we want it to trigger a warning only and not fail hard we have segmented it out
# Maybe due for a rework once we have better understood how critical resolution jitter is for making claims about the measurement
def add_effective_resolution_and_jitter(df):

    df['effective_resolution'] = df.groupby(['detail_name', 'unit'])['time'].diff()
    df['resolution_max'] = df.groupby(['detail_name', 'unit'])['effective_resolution'].transform('max')
    df['resolution_avg'] = df.groupby(['detail_name', 'unit'])['effective_resolution'].transform('mean')
    df['resolution_95p'] = df.groupby(['detail_name', 'unit'])['effective_resolution'].transform(lambda x: x.quantile(0.95))
    df = df.drop(columns=['effective_resolution'])

    return df
