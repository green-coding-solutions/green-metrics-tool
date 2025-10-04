import re

from lib.db import DB

class Notes():

    def __init__(self):
        self.__notes = [] # notes may have duplicate timestamps, therefore list and no dict structure

    def get_notes(self):
        return self.__notes


    def save_to_db(self, run_id):

        for note in self.__notes:
            DB().query("""
                    INSERT INTO notes
                    ("run_id", "detail_name", "note", "time", "created_at")
                    VALUES
                    (%s, %s, %s, %s, NOW())
                    """,
                       params=(run_id, note['detail_name'], note['note'], int(note['timestamp']))
                       )
    def parse_and_add_notes(self, detail_name, data):
        for match in re.findall(r'^(\d{16}) (.+)$', data, re.MULTILINE):
            self.__notes.append({'note': match[1], 'detail_name': detail_name, 'timestamp': match[0]})

    def add_note(self, note, detail_name, timestamp):
        self.__notes.append({'note': note , 'detail_name': detail_name, 'timestamp': timestamp})

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('run_id', help='Please supply a run_id to attribute the measurements to')

    args = parser.parse_args()  # script will exit if arguments not present

    notes = Notes()
    notes.parse_and_add_notes('my container', '1234567890123456 My note')
    notes.save_to_db(args.run_id)
