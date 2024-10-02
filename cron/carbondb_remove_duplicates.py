import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

from lib.db import DB

def remove_duplicates():
    DB().query("""
        DELETE FROM carbondb_energy_data a
        USING carbondb_energy_data b
        WHERE a.ctid < b.ctid
        AND a.time_stamp = b.time_stamp
        AND a.machine = b.machine
        AND a.energy_value = b.energy_value;
    """)


# pylint: disable=broad-except
if __name__ == '__main__':
    remove_duplicates()
