import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

from lib.db import DB

def remove_duplicates():
    DB().query("""
       DELETE FROM carbondb_energy_data
       WHERE ctid NOT IN (
           SELECT min(ctid)
           FROM carbondb_energy_data
           GROUP BY time_stamp, machine, energy_value
       )
    """)


# pylint: disable=broad-except
if __name__ == '__main__':
    remove_duplicates()
