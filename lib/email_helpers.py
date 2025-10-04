import smtplib
import ssl
from datetime import datetime, timedelta
#from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from lib.global_config import GlobalConfig
import math

def send_email(receiver, subject, message_input):

    config = GlobalConfig().config


    # message may not contain lines longer than 1000 chars (incl. \r\n) as some SMTP servers complain

    message_safe = []

    for line in message_input.splitlines():
        if (length := len(line)) > 998:
            chunk_length = math.floor(length / 998)
            chunks = [line[i:i+chunk_length] for i in range(0, length, chunk_length)]
            message_safe.extend(chunks)
        else:
            message_safe.append(line)

    message = '\n'.join(message_safe)
    message = f"{message}\n\n---\n{config['cluster']['metrics_url']}"

    # body_html = f"""
    # <html>
    #   <body>
    #     <pre>{message}</pre> <!-- if HTML is ever enable we need to make lines significantly shorter here as this exceeds 998 charaters with the markup -->
    #   </body>
    # </html>
    # """

#    msg = MIMEMultipart("alternative")
    msg = MIMEText(message, "plain")

    msg["From"] = config['smtp']['sender']
    msg["To"] = receiver
    msg["Subject"] = subject[0:998] # maximum of 1000 characters + \r\n
    msg["Expires"] = (datetime.utcnow() + timedelta(days=7)).strftime('%a, %d %b %Y %H:%M:%S +0000')

    if config['admin']['email_bcc']:
        receiver = [receiver] # make a list
        msg['Bcc'] = config['admin']['email_bcc']
        receiver.append(config['admin']['email_bcc'])



    # Attach the plain text and HTML parts - legacy
#    part1 = MIMEText(message, "plain")
#    part2 = MIMEText(body_html, "html")
#    msg.attach(part1)
#    msg.attach(part2)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(config['smtp']['server'], config['smtp']['port'], context=context) as server:
        # No need to set server.auth manually. server.login will iterater over all available methods
        # see https://github.com/python/cpython/blob/main/Lib/smtplib.py
        server.login(config['smtp']['user'], config['smtp']['password'])
        server.sendmail(config['smtp']['sender'], receiver, msg.as_string())

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
