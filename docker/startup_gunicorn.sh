#!/bin/sh
source /var/www/startup/venv/bin/activate

/var/www/startup/venv/bin/gunicorn \
--workers=2 \
--access-logfile=- \
--error-logfile=- \
--worker-tmp-dir=/dev/shm \
--threads=4 \
--worker-class=gthread \
--bind unix:/tmp/green-coding-api.sock \
-m 007 \
--user www-data \
--chdir /var/www/green-metrics-tool/api \
-k uvicorn.workers.UvicornWorker \
main:app