cd /var/www/green-metrics-tool/api
/etc/init.d/nginx start
/bin/gunicorn --workers 3 --bind unix:/tmp/green-metrics-tool/green-coding-api.sock -m 007 wsgi:app --user www-data --error-logfile /var/log/gunicorn-error.log