#pylint: disable=import-error,wrong-import-position

from html import escape
from re import fullmatch

from db import DB

class Notes():

    def __init__(self):
        self.__notes = [] # notes may have duplicate timestamps, therefore list and no dict structure

    def get_notes(self):
        return self.__notes


    def save_to_db(self, project_id):

        for note in self.__notes:
            DB().query("""
                    INSERT INTO notes
                    ("project_id", "detail_name", "note", "time", "created_at")
                    VALUES
                    (%s, %s, %s, %s, NOW())
                    """,
                       params=(project_id, escape(note['detail_name']), escape(note['note']), int(note['timestamp']))
                       )

    def parse_note(self, line):
        if match := fullmatch(r'^(\d{16}) (.+)', line):
            return int(match[1]), match[2]
        return None

    def add_note(self, note):
        self.__notes.append(note)

if __name__ == '__main__':
    import argparse
    import time

    parser = argparse.ArgumentParser()
    parser.add_argument('project_id', help='Please supply a project_id to attribute the measurements to')

    args = parser.parse_args()  # script will exit if arguments not present

    notes = Notes()
    notes.add_note({'note': 'This is my note',
                 'timestamp': int(time.time_ns() / 1000),
                 'detail_name': 'Arnes_ Container'})
    notes.save_to_db(args.project_id)
