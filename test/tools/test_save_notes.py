import os
import sys
import time
from unittest.mock import MagicMock

import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{CURRENT_DIR}/../../tools")
sys.path.append(f"{CURRENT_DIR}/../../lib")

# pylint: disable=import-error,wrong-import-position
from save_notes import save_notes
from db import DB


def test_invalid_string_timestamp():
    with pytest.raises(ValueError):
        save_notes(
            "test_project_id",
            [
                {
                    "note": "This is my note",
                    "timestamp": 'string_instead_of_time',
                    "detail_name": "Test_Container",
                }
            ],
        )

def test_string_timestamp():
    mock_db = DB()
    mock_db.query = MagicMock()

    save_notes(
        "test_project_id",
        [
            {
                "note": "This is my note",
                "timestamp": str(int(time.time_ns() / 1000)),
                "detail_name": "Test_Container",
            }
        ],
    )
    mock_db.query.assert_called_once()

def test_shorter_timestamp():
    with pytest.raises(ValueError):
        save_notes(
            "test_project_id",
            [
                {
                    "note": "This is my note",
                    "timestamp": int(time.time()),
                    "detail_name": "Test_Container",
                }
            ],
        )

def test_good_timestamp():
    mock_db = DB()
    mock_db.query = MagicMock()

    save_notes(
        "test_project_id",
        [
            {
                "note": "This is my note",
                "timestamp": int(time.time_ns() / 1000),
                "detail_name": "Test_Container",
            }
        ],
    )
    mock_db.query.assert_called_once()
