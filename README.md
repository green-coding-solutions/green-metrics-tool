## Introduction

This repository contains the command line tools to schedule and run the measurement report
as well as a web interface to view the measured metrics in some nice charts.

## Measurement methodology

The software can orchestrate Docker containers according to a given specificaion in a usage-flow.json file.

These containers will be setup on the host system and the testing specification in the usage-flow will be
run by sending the commands to the containers accordingly.

During this process the performance metrics of the containers are read through the stream of 
`docker stats`.

The current limitation of this approach is:
- The resolution of 1s is pretty low
- Docker stats gives sometime out different value than top / /proc/stat depending on your OS configuration
- It does not directly translate into energy without an appropriate transfer model.

These problems are currently addressed by doing research on either using onboard hardware sensors or measuring 
the electrical signals directly on-chip or on the cables of the machine.

We hope to refine the approach soon and update the tool accordingly (Thanks for @mrchrisadams requesting this clarification)

The next part README will guide you through the installation on your server / cloud instance.

## Installation

The tool requires a linux distribution as foundation, a webserver (instructions only give for NGINX, but any webserver will do)
python3 including some packages and docker installed (rootless optional).

We will directly install to /var/www as the tool should be run on a dedicated node anyway.
This is because of the competing resource allocation when run in a shared mode and also
because of security concerns.
We recommend to fully reset the node after every run, so no data from the previous run
remains in memory or on disk.

`git clone https://github.com/green-coding-berlin/green-metrics-tool /var/www`

`sudo apt update`

`sudo apt dist-upgrade -y`

`sudo apt install postgresql python3 python3-pip gunicorn nginx docker.io libpq-dev python-dev postgresql-contrib -y`

`pip3 install psycopg2 flask`


### Docker
Docker config should be finished right after installing through apt.

If you want rootless mode however be sure to follow the instructions here: https://docs.docker.com/engine/security/rootless/
After running the dockerd-rootless-setuptool.sh script, you may need to add some lines to your .bashrc file.

And you must also enable the cgroup2 support with the metrics granted for the user: https://rootlesscontaine.rs/getting-started/common/cgroup2/
Make sure to also enable the CPU, CPUTSET, and I/O delegation.

### Postgres
`sudo -i -u postgres`

`createuser my_user -P # and then type password`

`createdb --encoding=UTF-8 --owner=my_user my_user # DB is often already created with previous command`

`psql # make sure you are postgres user (whoami)`

this command in psql: ` ALTER USER my_user WITH SUPERUSER;`

leave the psql shell (ctrl+c)

`psql -U my_user # needs PW entry`

this command in psql: `CREATE EXTENSION "uuid-ossp";`

leave the psql shell (ctrl+c)

make sure you are a postgres user with `sudo -i -u postgres`

`psql` 

this command in psql: `ALTER USER my_user WITH SUPERUSER;`

leave the psql shell (ctrl+c)

now we import the structure

`psql -U my_user < /var/www/structure.sql`


#### Postgres Remote access (optional)
check first if 12 is really used version and then maybe replace number in next command

`echo "listen_addresses = '*'" >> /etc/postgresql/12/main/postgresql.conf`

`sudo nano /etc/postgresql/12/main/pg_hba.conf`

add the following line to the config

`host all all 0.0.0.0/0 md5`

maybe even remove other hosts as needed. Then reload

`sudo systemctl reload postgresql`

### Webservice
we are using `/var/www/html` for static files and as document root
and `/var/www/api` for the API

all must be owned by www-data (or the nginx user if different)

`sudo chwon -R /var/www www-data:www-data`

now we replace the references in the code with the real server address you are running on
`cd /var/www`

`sed -i "s/https:\/\/green-metric\.codetactics\.de/YOUR_URL_OR_IP_ESCAPED_HERE/" cron/send_email.py`

`sed -i "s/https:\/\/green-metric\.codetactics\.de/YOUR_URL_OR_IP_ESCAPED_HERE/" website/index.html`

`sed -i "s/https:\/\/green-metric\.codetactics\.de/YOUR_URL_OR_IP_ESCAPED_HERE/" website/request.html`


#### Gunicorn
test if gunicorn is working in general
`gunicorn --bind 0.0.0.0:5000 wsgi:app`

if all is working, we create the service for gunicorn
`sudo nano /etc/systemd/system/green-coding-api.service`

paste this:
```
[Unit]
Description=Gunicorn instance to serve Green Coding API
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/api
ExecStart=/bin/gunicorn --workers 3 --bind unix:green-coding-api.sock -m 007 wsgi:app

[Install]
WantedBy=multi-user.target
```

`sudo systemctl enable --now green-coding-api.service`

#### NGINX

`sudo nano /etc/nginx/sites-available/green-coding-api`

Paste this, but change "your-domain.com" to either your domain or the server ip:
```
server {
    listen 8080;
    server_name your_domain.com www.your_domain.com;

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/api/green-coding-api.sock;
    }
}
```

`sudo ln -s /etc/nginx/sites-available/green-coding-api /etc/nginx/sites-enabled/`

and we also must change the default document root

`sudo nano /etc/nginx/sites-available/default`

here you must modify the root directive to: `root /var/www/website;`

Then reload all:
`sudo systemctl restart nginx`

## Configuring the command line application
Create the file `/var/www/config.yml` with the correct Database and SMTP credentials. 
A sample setup for the file can be found in `/var/www/config.yml.example`


***Now create a snapshot of the machine to reaload this state later on***


## Testing the command line application
First you have to create a project through the web interface, so the cron runner will pick it up from the database.

Go to http://YOUR_CONFIGURED_URL/request.html
Note: You must enter a Github Repo URL with a repository that has the usage_scenario.json in a valid format. Consult [Github Repository for the Demo software](https://github.com/green-coding-berlin/green-metric-demo-software) for more info

After creating project run:

`/var/www/cron/runner.sh cron`

## Implement a cronjob (optional)
Run this command as the user for which docker is configured:
`crontab -e`

Then install following cron for `root` to run job every 15 min:

`*/15     *       *       *       *       rm -Rf /tmp/repo; python3 /var/www/cron/runner.py cron`

If you have no MTA installed you can also pipe the output to a specific file like so:

`*/15     *       *       *       *       rm -Rf /tmp/repo; python3 /var/www/cron/runner.py cron 2>&1 >> /var/log/cron-green-metric.log`

If you have docker configured to run in rootless mode be sure to issue the exports for the cron command beforehand.
A cronjob in the `crontab -e` of the non-root may look similar to this one:

`
DOCKER_HOST=unix:///run/user/1000/docker.sock
*/5     *       *       *       *       export PATH=/home/USERNAME/bin:$PATH; rm -Rf /tmp/repo; python3 /var/www/cron/runner.py cron 2>&1 >> /var/log/cron-green-metric.log`

Also make sure that `/var/log/cron-green-metric.log` is writeable by the user:

`sudo touch /var/log/cron-green-metric.log && sudo chown MY_USER:MY_USER /var/log/cron-green-metric.log`

### Locking and Timeout for cron
Depending on how often you run the cronjob and how long your jobs are the cronjobs may interleave which
will cause problems.

On a typical Linux system you can use timeout / flock to prevent this.
This example creates a exclusive lock and timeouts to 4 minutes

`
DOCKER_HOST=unix:///run/user/1000/docker.sock
*/5     *       *       *       *       export PATH=/home/USERNAME/bin:$PATH
; timeout 240s flock -nx /var/lock/greencoding-runner rm -Rf /tmp/repo && python3 /var/www/cron/runner.py cron 2>&1 >> /var/log/cron-green-metric.log`
