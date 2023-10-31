from unittest.mock import patch
import pytest

from lib.notes import Notes
from tests import test_functions as Tests

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
@patch('lib.db.DB.query')
def test_valid_timestamp(mock_query, run_id, note, detail, timestamp):
    mock_query.return_value = None  # Replace with the desired return value

    notes = Notes()
    notes.add_note({"note": note, "detail_name": detail, "timestamp": timestamp})
    notes.save_to_db(run_id)

    mock_query.assert_called_once()
