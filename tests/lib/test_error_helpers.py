from lib import error_helpers
from lib.db import DB
from tests import test_functions as Tests

OPENSSH_EXAMPLE_PRIVATE_KEY = Tests.OPENSSH_EXAMPLE_PRIVATE_KEY


def _last_system_log():
    return DB().fetch_one(
        "SELECT title, message, level FROM system_logs WHERE title = 'Green Metrics Tool Error' ORDER BY id DESC LIMIT 1",
        fetch_mode='dict',
    )


def test_log_error_redacts_uri_credentials_in_stderr_and_db(capsys):
    error_helpers.log_error('Clone failed', repo_url='https://admin:s3cr3t@github.com/org/repo.git')

    captured = capsys.readouterr()
    assert 'admin' not in captured.err
    assert 's3cr3t' not in captured.err
    assert '*****GMT-REDACTED*****' in captured.err

    log_row = _last_system_log()
    assert log_row is not None, Tests.assertion_info('a system_logs row', 'none found')
    assert 'admin' not in log_row['message']
    assert 's3cr3t' not in log_row['message']
    assert '*****GMT-REDACTED*****' in log_row['message']


def test_log_error_redacts_private_keys_in_stderr_and_db(capsys):
    error_helpers.log_error('SSH connection failed', ssh_key=OPENSSH_EXAMPLE_PRIVATE_KEY)

    captured = capsys.readouterr()
    assert OPENSSH_EXAMPLE_PRIVATE_KEY not in captured.err
    assert 'BEGIN OPENSSH PRIVATE KEY' not in captured.err
    assert '*****GMT-REDACTED*****' in captured.err

    log_row = _last_system_log()
    assert log_row is not None, Tests.assertion_info('a system_logs row', 'none found')
    assert OPENSSH_EXAMPLE_PRIVATE_KEY not in log_row['message']
    assert 'BEGIN OPENSSH PRIVATE KEY' not in log_row['message']
    assert '*****GMT-REDACTED*****' in log_row['message']


def test_log_error_leaves_clean_messages_untouched(capsys):
    error_helpers.log_error('Simple failure', detail='nothing sensitive here')

    captured = capsys.readouterr()
    assert 'nothing sensitive here' in captured.err
    assert '*****GMT-REDACTED*****' not in captured.err

    log_row = _last_system_log()
    assert log_row is not None, Tests.assertion_info('a system_logs row', 'none found')
    assert 'nothing sensitive here' in log_row['message']
    assert '*****GMT-REDACTED*****' not in log_row['message']
