import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from bisect import bisect_right
from decimal import Decimal
from io import StringIO

from lib.db import DB

DERIVED_METRIC = 'psu_carbon_elephant_machine'

def calculate_co2_intensity(run_id):
    carbon_intensity_metrics = DB().fetch_all('''
        SELECT id, metric, detail_name
        FROM measurement_metrics
        WHERE run_id = %s AND metric LIKE 'carbon_intensity_%%' AND unit = 'gCO2e/kWh'
        ORDER BY metric ASC, detail_name ASC
    ''', params=(run_id, ))

    if not carbon_intensity_metrics:
        return

    machine_energy_metrics = DB().fetch_all('''
        SELECT id, metric, detail_name
        FROM measurement_metrics
        WHERE run_id = %s AND metric LIKE '%%_energy_%%_machine' AND unit = 'uJ'
        ORDER BY metric ASC, detail_name ASC
    ''', params=(run_id, ))

    if not machine_energy_metrics:
        return


    for carbon_metric_id, carbon_metric, carbon_detail_name in carbon_intensity_metrics:
        carbon_values = DB().fetch_all('''
            SELECT time, value
            FROM measurement_values
            WHERE measurement_metric_id = %s
            ORDER BY time ASC
        ''', params=(carbon_metric_id, ))

        if not carbon_values:
            continue

        for energy_metric_id, energy_metric, energy_detail_name in machine_energy_metrics:
            energy_values = DB().fetch_all('''
                SELECT time, value
                FROM measurement_values
                WHERE measurement_metric_id = %s
                ORDER BY time ASC
            ''', params=(energy_metric_id, ))

            if not energy_values:
                continue

            detail_name = f"{energy_metric}_{energy_detail_name}_{carbon_metric}_{carbon_detail_name}"
            derived_metric_id = DB().fetch_one('''
                INSERT INTO measurement_metrics (run_id, metric, detail_name, unit)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            ''', params=(run_id, DERIVED_METRIC, detail_name, 'ugCO2e'))[0]

            csv_buffer = StringIO()
            carbon_times = [entry[0] for entry in carbon_values]
            carbon_intensities = [entry[1] for entry in carbon_values]

            for energy_time, energy_value in energy_values:
                carbon_index = bisect_right(carbon_times, energy_time) - 1
                carbon_index = max(carbon_index, 0)

                current_carbon_value = carbon_intensities[carbon_index]
                carbon_ug = Decimal(energy_value) * Decimal(current_carbon_value) / Decimal(3_600_000)
                csv_buffer.write(f"{derived_metric_id},{round(carbon_ug)},{energy_time}\n")

            csv_buffer.seek(0)
            DB().copy_from(
                csv_buffer,
                table='measurement_values',
                sep=',',
                columns=('measurement_metric_id', 'value', 'time')
            )
            csv_buffer.close()

