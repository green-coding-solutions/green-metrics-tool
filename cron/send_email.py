def send_report_email(receiver_email, report_id):
    import yaml
    import os
    with open("{path}/../config.yml".format(path=os.path.dirname(os.path.realpath(__file__)))) as config_file:
        config = yaml.load(config_file,yaml.FullLoader)

    import smtplib, ssl
    message = """\
From: {smtp_sender}
To: {receiver_email}
Subject: Your Green Metric report is ready

Your report is now accessible under the URL: http://127.0.0.1:8080/?id={report_id}

--
Green Coding Berlin
https://www.green-coding.org

    """
    message = message.format(
        receiver_email=receiver_email,
        report_id=report_id,
        smtp_sender=config['smtp']['sender'])

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(config['smtp']['server'], config['smtp']['port'], context=context) as server:
        # No need to set server.auth manually. server.login will iterater over all available methods
        # see https://github.com/python/cpython/blob/main/Lib/smtplib.py
        server.login(config['smtp']['user'], config['smtp']['password'])

        server.sendmail(config['smtp']['sender'], receiver_email, message)
