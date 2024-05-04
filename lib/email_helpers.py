import smtplib
import ssl

from lib.global_config import GlobalConfig

def send_email(receiver, subject, message):
    config = GlobalConfig().config

    receiver = [receiver]
    data = f"From: {config['smtp']['sender']}\n"
    data += f"To: {receiver}\n"
    data += f"Subject: {subject}\n"
    if config['admin']['email_bcc']:
        data += f"Bcc: {config['admin']['email_bcc']}\n"
        receiver.append(config['admin']['email_bcc'])
    data += f"\n{message}\n\n---\n{config['cluster']['metrics_url']}"

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(config['smtp']['server'], config['smtp']['port'], context=context) as server:
        # No need to set server.auth manually. server.login will iterater over all available methods
        # see https://github.com/python/cpython/blob/main/Lib/smtplib.py
        server.login(config['smtp']['user'], config['smtp']['password'])
        server.sendmail(config['smtp']['sender'], receiver, data.encode('utf-8'))

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('receiver', help='Please supply a receiver email to send the email to')

    args = parser.parse_args()  # script will exit if arguments is not present

    send_email(args.receiver, "My subject", "My custom message")
