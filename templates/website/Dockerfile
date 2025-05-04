# Inspiration for the config docker build and config file from: https://github.com/salrashid123/squid_proxy
FROM ubuntu
RUN apt-get -y update && apt-get install -y squid-openssl

WORKDIR /apps/

ADD tls-ca.key /apps/tls-ca.key
ADD tls-ca.crt /apps/tls-ca.crt
ADD squid.conf.intercept-cache /apps/squid.conf.intercept-cache

RUN mkdir -p /apps/squid/var/lib/
RUN mkdir -p /apps/squid/var/cache
RUN mkdir -p /apps/squid/var/logs/

RUN chown -R proxy:proxy /apps/
RUN /usr/lib/squid/security_file_certgen -c -s /apps/squid/var/lib/ssl_db -M 4MB
RUN /usr/sbin/squid -N -f /apps/squid.conf.intercept-cache -z
RUN chown -R proxy:proxy /apps/
RUN chgrp -R 0 /apps && chmod -R g=u /apps

RUN chown -R proxy:proxy /apps/


EXPOSE 3128

ENTRYPOINT ["/usr/sbin/squid", "-NsY", "-d", "1", "-f", "/apps/squid.conf.intercept-cache"]
