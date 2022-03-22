def send_report_email(receiver_email, report_id):
    import yaml
    import os
    with open("{path}/../config.yml".format(path=os.path.dirname(os.path.realpath(__file__)))) as config_file:
        config = yaml.load(config_file,yaml.FullLoader)

    import smtplib, ssl

    port = 465  # For SSL
    smtp_server = "smtp.mailfence.com"
    sender_email = "info@green-coding.org"
    password = config['smtp']['password']
    message = """\
To: {receiver_email}
From: info@green-coding.org
Subject: Your Green Metric report is ready

Your report is now accessible under the URL: https://green-metric.codetactics.de/?id={report_id}

--
Green Coding Berlin
https://www.green-coding.org

    """

    message = message.format(receiver_email=receiver_email, report_id=report_id)
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login("JonathanSaudhof", password)
        server.sendmail(sender_email, receiver_email, message)
