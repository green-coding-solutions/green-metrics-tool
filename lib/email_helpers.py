import smtplib
import ssl

from lib.global_config import GlobalConfig

def send_email(message, receiver_email):
    config = GlobalConfig().config
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(config['smtp']['server'], config['smtp']['port'], context=context) as server:
        # No need to set server.auth manually. server.login will iterater over all available methods
        # see https://github.com/python/cpython/blob/main/Lib/smtplib.py
        server.login(config['smtp']['user'], config['smtp']['password'])
        server.sendmail(config['smtp']['sender'], receiver_email, message.encode('utf-8'))

def send_admin_email(subject, body):
    message = """\
From: {smtp_sender}
To: {receiver_email}
Subject: {subject}

{body}

--
{url}"""

    config = GlobalConfig().config
    message = message.format(
        subject=subject,
        body=body,
        url=config['cluster']['metrics_url'],
        receiver_email=config['admin']['email'],
        smtp_sender=config['smtp']['sender'])
    send_email(message, [config['admin']['email'], config['admin']['bcc_email']])


def send_error_email(receiver_email, error, run_id=None, name=None, machine=None):
    message = """\
From: {smtp_sender}
To: {receiver_email}
Bcc: {bcc_email}
Subject: Your Green Metrics analysis has encountered problems

Unfortunately, your Green Metrics analysis has run into some issues and could not be completed.

Name: {name}
Run Id: {run_id}
Machine: {machine}
Link: {link}

{errors}

--
{url}"""

    config = GlobalConfig().config
    link = 'No link available'
    if run_id is not None:
        link = f"Link: {config['cluster']['metrics_url']}/stats.html?id={run_id}"
    message = message.format(
        receiver_email=receiver_email,
        errors=error,
        name=name,
        machine=machine,
        bcc_email=config['admin']['bcc_email'],
        url=config['cluster']['metrics_url'],
        run_id=run_id,
        link=link,
        smtp_sender=config['smtp']['sender'])
    send_email(message, [receiver_email, config['admin']['bcc_email']])


def send_report_email(receiver_email, run_id, name, machine=None):
    message = """\
From: {smtp_sender}
To: {receiver_email}
Bcc: {bcc_email}
Subject: Your Green Metric report is ready

Run Name: {name}
Machine: {machine}

Your report is now accessible under the URL: {url}/stats.html?id={run_id}

--
{url}"""

    config = GlobalConfig().config
    message = message.format(
        receiver_email=receiver_email,
        run_id=run_id,
        machine=machine,
        name=name,
        bcc_email=config['admin']['bcc_email'],
        url=config['cluster']['metrics_url'],
        smtp_sender=config['smtp']['sender'])
    send_email(message, [receiver_email, config['admin']['bcc_email']])


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('receiver_email', help='Please supply a receiver_email to send the email to')
    parser.add_argument('run_id', help='Please supply a run_id to include in the email')

    args = parser.parse_args()  # script will exit if arguments is not present

    send_report_email(args.receiver_email, args.run_id, "My custom name")
