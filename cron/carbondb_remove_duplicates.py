import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

from lib.global_config import GlobalConfig
from lib.db import DB
from lib import error_helpers

def remove_duplicates():
    DB().query("""
        DELETE FROM carbondb_energy_data a
        USING carbondb_energy_data b
        WHERE a.ctid < b.ctid
        AND a.time_stamp = b.time_stamp
        AND a.machine = b.machine
        AND a.energy_value = b.energy_value;
    """)


if __name__ == '__main__':
    try:
        remove_duplicates()
    except Exception as exc: # pylint: disable=broad-except
        error_helpers.log_error(f'Processing in {__file__} failed.', exception=exc, machine=GlobalConfig().config['machine']['description'])
