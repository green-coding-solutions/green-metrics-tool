import os
import sys
import time

import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{CURRENT_DIR}/../../tools")
sys.path.append(f"{CURRENT_DIR}/../../lib")

# pylint: disable=import-error,wrong-import-position
from save_notes import save_notes
import utils


def test_invalid_string_timestamp():
    with pytest.raises(ValueError) as err:
        save_notes(
            "e55675c5-8f7b-4d21-a4f7-d2417e23a44b",
            [
                {
                    "note": "This is my note",
                    "timestamp": 'string_instead_of_time',
                    "detail_name": "Test_Container",
                }
            ],
        )
    expected_exception = "Note timestamp did not match expected format"
    assert expected_exception in str(err.value), \
        utils.assertion_info(f"Exception: {expected_exception}", str(err.value))

def test_string_timestamp():
    save_notes(
        "e55675c5-8f7b-4d21-a4f7-d2417e23a44b",
        [
            {
                "note": "This is my note",
                "timestamp": str(int(time.time_ns() / 1000)),
                "detail_name": "Test_Container",
            }
        ],
    )

def test_shorter_timestamp():
    with pytest.raises(ValueError) as err:
        save_notes(
            "e55675c5-8f7b-4d21-a4f7-d2417e23a44b",
            [
                {
                    "note": "This is my note",
                    "timestamp": int(time.time()),
                    "detail_name": "Test_Container",
                }
            ],
        )
    expected_exception = "Note timestamp did not match expected format"
    assert expected_exception in str(err.value), \
        utils.assertion_info(f"Exception: {expected_exception}", str(err.value))

def test_good_timestamp():
    save_notes(
        "e55675c5-8f7b-4d21-a4f7-d2417e23a44b",
        [
            {
                "note": "This is my note",
                "timestamp": int(time.time_ns() / 1000),
                "detail_name": "Test_Container",
            }
        ],
    )
