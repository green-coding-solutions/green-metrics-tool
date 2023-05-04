#pylint: disable=wrong-import-position,import-error
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../../api")

import api_helpers


def test_escape_dict():
    messy_dict = {"link": '<a href="http://www.github.com">Click me</a>'}
    escaped = api_helpers.escape_dict(messy_dict.copy())
    assert messy_dict['link'] != escaped['link']
