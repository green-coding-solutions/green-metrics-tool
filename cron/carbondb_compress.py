import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

from lib.global_config import GlobalConfig
from lib.db import DB
from lib import error_helpers

def compress_data():
    query = """
        INSERT INTO carbondb_energy_data_day (
            type,
            company,
            machine,
            project,
            tags,
            date,
            energy_sum,
            co2_sum,
            carbon_intensity_avg,
            record_count
        )
        SELECT
            e.type,
            e.company,
            e.machine,
            e.project,
            e.tags,
            DATE_TRUNC('day', TO_TIMESTAMP(e.time_stamp / 1000000)),
            SUM(e.energy_value) AS energy_sum,
            SUM(e.co2_value) AS co2_sum,
            AVG(e.carbon_intensity) AS carbon_intensity_avg,
            COUNT(*) AS record_count
        FROM
            carbondb_energy_data e
        LEFT JOIN
            carbondb_energy_data_day d ON e.machine = d.machine
                                        AND e.project = d.project
                                        AND DATE_TRUNC('day', TO_TIMESTAMP(e.time_stamp / 1000000)) = d.date
        GROUP BY
            e.type,
            e.company,
            e.machine,
            e.project,
            e.tags,
            DATE_TRUNC('day', TO_TIMESTAMP(e.time_stamp / 1000000))
        ON CONFLICT (type, company, machine, project, tags, date) DO UPDATE
        SET
            energy_sum = EXCLUDED.energy_sum,
            co2_sum = EXCLUDED.co2_sum,
            carbon_intensity_avg = EXCLUDED.carbon_intensity_avg,
            record_count = EXCLUDED.record_count;
    """
    print(DB().query(query))

if __name__ == '__main__':
    try:
        compress_data()
    except Exception as exc: # pylint: disable=broad-except
        error_helpers.log_error(f'Processing in {__file__} failed.', exception=exc, machine=GlobalConfig().config['machine']['description'])
