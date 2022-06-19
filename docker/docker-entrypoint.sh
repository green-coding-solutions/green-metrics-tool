cd /var/www/green-metrics-tool/api
/etc/init.d/nginx start
/bin/gunicorn --workers 3 --bind unix:/tmp/green-coding-api.sock -m 007 api:app --user www-data -k uvicorn.workers.UvicornWorker --error-logfile /var/log/gunicorn-error.log