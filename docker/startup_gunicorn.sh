#!/bin/sh
source /var/www/startup/.venv/bin/activate

# Warns in the postgres server log about outdated extensions. Backgrounded so it never delays startup
python3 /var/www/green-metrics-tool/tools/check_postgres_extensions.py &

/var/www/startup/.venv/bin/gunicorn \
--workers=8 \
--access-logfile=- \
--error-logfile=- \
--worker-tmp-dir=/dev/shm \
--worker-class=uvicorn_worker.UvicornWorker \
--bind unix:/tmp/gmt-sockets/api.sock \
-m 007 \
--user www-data \
--chdir /var/www/green-metrics-tool/api \
-k uvicorn_worker.UvicornWorker \
main:app