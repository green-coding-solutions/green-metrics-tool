#pylint: disable=wrong-import-position,import-error
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../../api")

import api_helpers


def test_sanitize_dict():
    messy_dict = {"link": '<a href="http://www.github.com">Click me</a>'}
    sanitized = api_helpers.sanitize(messy_dict.copy())
    assert messy_dict['link'] != sanitized['link']
