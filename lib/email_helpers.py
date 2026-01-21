import smtplib
import ssl
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from lib.global_config import GlobalConfig
import math

# message may not contain lines longer than 1000 chars (incl. \r\n) as some SMTP servers complain
def chunk_message(message, max_chunk_length=998):
    message_chunked = []
    for line in message.splitlines():
        if (length := len(line)) > max_chunk_length:
            chunk_length = math.ceil(length / max_chunk_length)
            chunks = [line[i*998:(i+1)*998] for i in range(0, chunk_length)]
            message_chunked.extend(chunks)
        else:
            message_chunked.append(line)
    return message_chunked

def send_email(receiver, subject, text_message, html_message=None):

    config = GlobalConfig().config

    # Chunking only needed for the text part which happens if it does
    # not need encoding and is ASCII only
    # HTML is always encoded and will thus be chunkged by email lib
    text_message_chunked = chunk_message(text_message)
    text_message_chunked = '\n'.join(text_message_chunked)

    if html_message:
        msg = MIMEMultipart("alternative")
        part1 = MIMEText(text_message_chunked, "plain", "utf-8")
        msg.attach(part1)
        part2 = MIMEText(html_message, "html", "utf-8")
        msg.attach(part2)
    else:
        msg = MIMEText(text_message_chunked, "plain")


    msg["From"] = config['smtp']['sender']
    msg["To"] = receiver
    msg["Subject"] = subject[0:989] # maximum of 1000 characters - \r\n  - "subject: "
    msg["Expires"] = (datetime.utcnow() + timedelta(days=7)).strftime('%a, %d %b %Y %H:%M:%S +0000')

    recipients = [receiver]
    if config['admin']['email_bcc']:
        msg['Bcc'] = config['admin']['email_bcc']
        recipients.append(config['admin']['email_bcc'])


    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(config['smtp']['server'], config['smtp']['port'], context=context) as server:
        # No need to set server.auth manually. server.login will iterater over all available methods
        # see https://github.com/python/cpython/blob/main/Lib/smtplib.py
        server.login(config['smtp']['user'], config['smtp']['password'])
        server.sendmail(config['smtp']['sender'], recipients, msg.as_string())

if __name__ == '__main__':
    import argparse
    import os

    parser = argparse.ArgumentParser()
    parser.add_argument('receiver', help='Please supply a receiver email to send the email to')
    parser.add_argument('data', help='Please supply a message or a filename')

    args = parser.parse_args()  # script will exit if arguments is not present

    if os.path.exists(args.data):
        with open(args.data, encoding='UTF-8') as f:
            data = f.read()
    else:
        data = args.data

    send_email(args.receiver, "My subject", data)
