import smtplib
import ssl
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from lib.global_config import GlobalConfig

def send_email(receiver, subject, message):

    config = GlobalConfig().config


    message = f"{message}\n\n---\n{config['cluster']['metrics_url']}"
    body_html = f"""
    <html>
      <body>
        <pre>{message}</pre>
      </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["From"] = config['smtp']['sender']
    msg["To"] = receiver
    msg["Subject"] = subject
    msg["Expires"] = (datetime.utcnow() + timedelta(days=7)).strftime('%a, %d %b %Y %H:%M:%S +0000')

    if config['admin']['email_bcc']:
        receiver = [receiver] # make a list
        msg['Bcc'] = config['admin']['email_bcc']
        receiver.append(config['admin']['email_bcc'])

    # Attach the plain text and HTML parts
    part1 = MIMEText(message, "plain")
    part2 = MIMEText(body_html, "html")
    msg.attach(part1)
    msg.attach(part2)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(config['smtp']['server'], config['smtp']['port'], context=context) as server:
        # No need to set server.auth manually. server.login will iterater over all available methods
        # see https://github.com/python/cpython/blob/main/Lib/smtplib.py
        server.login(config['smtp']['user'], config['smtp']['password'])
        server.sendmail(config['smtp']['sender'], receiver, msg.as_string())

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('receiver', help='Please supply a receiver email to send the email to')

    args = parser.parse_args()  # script will exit if arguments is not present

    send_email(args.receiver, "My subject", "My custom message")
