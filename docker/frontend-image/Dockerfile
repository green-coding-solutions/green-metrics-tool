# Prebuilt GMT frontend: NGINX serving the static files from frontend/
#
# Build from the repository root, as the image needs frontend/ and docker/nginx/:
#   docker build -f docker/frontend-image/Dockerfile -t greencoding/gmt-frontend .
#
# Configuration happens at container start, see docker/frontend-image/README.md
FROM nginx:stable-alpine

ENV GMT_FRONTEND_ROOT=/var/www/green-metrics-tool/frontend

COPY frontend/ ${GMT_FRONTEND_ROOT}/

# config.js.example becomes the template that 40-gmt-frontend-config.sh fills from the GMT_*
# environment variables. It is moved out of the web root so it is not served. A local,
# install-generated config.js must never end up in the image.
RUN mkdir -p /usr/share/gmt-frontend \
    && mv ${GMT_FRONTEND_ROOT}/js/helpers/config.js.example /usr/share/gmt-frontend/config.js.template \
    && rm -f ${GMT_FRONTEND_ROOT}/js/helpers/config.js

# Same server block as a regular install without SSL. There is only this one server, so it
# answers for every host name.
COPY docker/nginx/frontend.conf.example /etc/nginx/conf.d/default.conf
RUN sed -i -e 's|#__DEFAULT__||g' -e 's|__METRICS_URL__|_|' /etc/nginx/conf.d/default.conf

# Run by the entrypoint of the nginx base image before nginx starts
COPY --chmod=755 docker/frontend-image/40-gmt-frontend-config.sh /docker-entrypoint.d/40-gmt-frontend-config.sh

EXPOSE 9142

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:9142/ || exit 1
