import os
import sys
from unittest.mock import MagicMock

import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{CURRENT_DIR}/../../tools")
sys.path.append(f"{CURRENT_DIR}/../../lib")

# pylint: disable=import-error,wrong-import-position
from save_notes import save_notes
from db import DB
import test_functions as Tests

invalid_test_data = [
    ("e55675c5-8f7b-4d21-a4f7-d2417e23a44b", "This is a note", "test", "string_instead_of_time"),
    ("e55675c5-8f7b-4d21-a4f7-d2417e23a44b", "This is a note", "test", 1679393122),
]
valid_test_data = [
    ("e55675c5-8f7b-4d21-a4f7-d2417e23a44b", "This is a note", "test", '1679393122123643'),
    ("e55675c5-8f7b-4d21-a4f7-d2417e23a44b", "This is a note", "test", 1679393122123643),
]


@pytest.mark.parametrize("project_id,note,detail,timestamp", invalid_test_data)
def test_invalid_timestamp(project_id, note, detail, timestamp):
    with pytest.raises(ValueError) as err:
        save_notes(
            project_id,
            [
                {
                    "note": note,
                    "detail_name": detail,
                    "timestamp": timestamp,
                }
            ],
        )
    expected_exception = "Note timestamp did not match expected format"
    assert expected_exception in str(err.value), \
        Tests.assertion_info(f"Exception: {expected_exception}", str(err.value))

@pytest.mark.parametrize("project_id,note,detail,timestamp", valid_test_data)
def test_valid_timestamp(project_id, note, detail, timestamp):
    mock_db = DB()
    mock_db.query = MagicMock()

    save_notes(
        project_id,
        [
            {
                "note": note,
                "detail_name": detail,
                "timestamp": timestamp,
            }
        ],
    )

    mock_db.query.assert_called_once()
