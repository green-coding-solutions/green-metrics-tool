import subprocess
import pytest

from lib import utils

@pytest.mark.parametrize('value', [
    'plain',
    '''This is a "string for ' me to know.''',
    "''",
    "it's $HOME `id` $(id) \\ ; | & *",
    'line one\nline two',
    '',
])
def test_quote_for_single_quotes_round_trips_through_shell(value):
    # the shell must hand back exactly the original value as one single argument
    output = subprocess.check_output(['sh', '-c', f"printf '%s' '{utils.quote_for_single_quotes(value)}'"], encoding='UTF-8')
    assert output == value

def test_quote_for_single_quotes_only_touches_single_quotes():
    assert utils.quote_for_single_quotes('''a "b" c''') == '''a "b" c'''
    assert utils.quote_for_single_quotes("a'b") == '''a'"'"'b'''
