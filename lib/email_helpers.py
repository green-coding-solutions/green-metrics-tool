import sys
import os
import smtplib
import ssl

from global_config import GlobalConfig

sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../lib')


def send_email(message, receiver_email):
    config = GlobalConfig().config

    if config['admin']['no_emails'] is True:
        return

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(config['smtp']['server'], config['smtp']['port'], context=context) as server:
        # No need to set server.auth manually. server.login will iterater over all available methods
        # see https://github.com/python/cpython/blob/main/Lib/smtplib.py
        server.login(config['smtp']['user'], config['smtp']['password'])
        server.sendmail(config['smtp']['sender'], receiver_email, message)


def send_admin_email(subject, body):
    config = GlobalConfig().config
    message = """\
From: {smtp_sender}
To: {receiver_email}
Subject: {subject}

{body}

--
Green Coding Berlin
https://www.green-coding.berlin

    """
    message = message.format(
        subject=subject,
        body=body,
        receiver_email=config['admin']['email'],
        smtp_sender=config['smtp']['sender'])
    send_email(message, config['admin']['email'])


def send_error_email(receiver_email, error, project_id=None):
    config = GlobalConfig().config
    message = """\
From: {smtp_sender}
To: {receiver_email}
Subject: Your Green Metrics analysis has encountered problems

Unfortunately, your Green Metrics analysis has run into some issues and could not be completed.

Project id: {project_id}
{errors}

--
Green Coding Berlin
https://www.green-coding.berlin

    """
    message = message.format(
        receiver_email=receiver_email,
        errors=error,
        project_id=project_id,
        smtp_sender=config['smtp']['sender'])
    send_email(message, receiver_email)


def send_report_email(receiver_email, report_id):
    config = GlobalConfig().config
    message = """\
From: {smtp_sender}
To: {receiver_email}
Subject: Your Green Metric report is ready

Your report is now accessible under the URL: {url}stats.html?id={report_id}

--
Green Coding Berlin
https://www.green-coding.berlin

    """
    message = message.format(
        receiver_email=receiver_email,
        report_id=report_id,
        url=config['project']['url'],
        smtp_sender=config['smtp']['sender'])
    send_email(message, receiver_email)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('receiver_email', help='Please supply a receiver_email to send the email to')
    parser.add_argument('report_id', help='Please supply a report_id to include in the email')

    args = parser.parse_args()  # script will exit if arguments is not present

    send_report_email(args.receiver_email, args.report_id)
