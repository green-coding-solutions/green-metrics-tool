import pytest

from lib.job.email import EmailJob
from lib.job.email_simple import EmailSimpleJob
from lib.job.email_report import EmailReportJob
from lib.db import DB
from tests import test_functions as Tests

OPENSSH_EXAMPLE_PRIVATE_KEY = Tests.OPENSSH_EXAMPLE_PRIVATE_KEY


def _job_row(job_id):
    return DB().fetch_one(
        'SELECT type, message FROM jobs WHERE id = %s',
        params=(job_id,),
        fetch_mode='dict',
    )


def test_email_job_cannot_be_used_directly():
    with pytest.raises(NotImplementedError):
        EmailJob.insert(user_id=1, email='foo@example.com', name='Test')


def test_insert_redacts_uri_credentials_in_db():
    job_id = EmailSimpleJob.insert(
        user_id=1,
        email='foo@example.com',
        name='Test',
        message='repo: https://admin:s3cr3t@github.com/org/repo.git',
    )

    job = _job_row(job_id)
    assert job is not None, Tests.assertion_info('a jobs row', 'none found')
    assert job['type'] == 'email-simple'
    assert 'admin' not in job['message']
    assert 's3cr3t' not in job['message']
    assert '*****GMT-REDACTED*****' in job['message']


def test_insert_redacts_private_keys_in_db():
    job_id = EmailSimpleJob.insert(
        user_id=1,
        email='foo@example.com',
        name='Test',
        message=f"Here is the key:\n{OPENSSH_EXAMPLE_PRIVATE_KEY}\nEnd of message",
    )

    job = _job_row(job_id)
    assert job is not None, Tests.assertion_info('a jobs row', 'none found')
    assert OPENSSH_EXAMPLE_PRIVATE_KEY not in job['message']
    assert 'BEGIN OPENSSH PRIVATE KEY' not in job['message']
    assert '*****GMT-REDACTED*****' in job['message']


def test_insert_leaves_clean_message_untouched_in_db():
    job_id = EmailSimpleJob.insert(
        user_id=1,
        email='foo@example.com',
        name='Test',
        message='nothing sensitive here',
    )

    job = _job_row(job_id)
    assert job is not None, Tests.assertion_info('a jobs row', 'none found')
    assert job['message'] == 'nothing sensitive here'
    assert '*****GMT-REDACTED*****' not in job['message']


def test_insert_without_message_stays_null_in_db():
    job_id = EmailReportJob.insert(
        user_id=1,
        email='foo@example.com',
        name='Test',
        run_id=None,
    )

    job = _job_row(job_id)
    assert job is not None, Tests.assertion_info('a jobs row', 'none found')
    assert job['type'] == 'email-report'
    assert job['message'] is None
