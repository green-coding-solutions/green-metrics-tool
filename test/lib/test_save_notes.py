import os
import sys
from unittest.mock import MagicMock

import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{CURRENT_DIR}/../../lib")

# pylint: disable=import-error,wrong-import-position
from notes import Notes
from db import DB
import test_functions as Tests

invalid_test_data = [
    ("72e54687-ba3e-4ef6-a5a1-9f2d6af26239", "This is a note", "test", "string_instead_of_time"),
]
valid_test_data = [
    ("72e54687-ba3e-4ef6-a5a1-9f2d6af26239", "This is a note", "test", '1679393122123643'),
    ("72e54687-ba3e-4ef6-a5a1-9f2d6af26239", "This is a note", "test", 1679393122123643),
]


@pytest.mark.parametrize("run_id,note,detail,timestamp", invalid_test_data)
def test_invalid_timestamp(run_id, note, detail, timestamp):
    with pytest.raises(ValueError) as err:
        notes = Notes()
        notes.add_note({"note": note,"detail_name": detail,"timestamp": timestamp,})
        notes.save_to_db(run_id)
    expected_exception = "invalid literal for int"
    assert expected_exception in str(err.value), \
        Tests.assertion_info(f"Exception: {expected_exception}", str(err.value))

@pytest.mark.parametrize("run_id,note,detail,timestamp", valid_test_data)
def test_valid_timestamp(run_id, note, detail, timestamp):
    mock_db = DB()
    mock_db.query = MagicMock()

    notes = Notes()
    notes.add_note({"note": note,"detail_name": detail,"timestamp": timestamp,})
    notes.save_to_db(run_id)
    mock_db.query.assert_called_once()
