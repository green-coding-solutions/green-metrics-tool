FROM alpine

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy

RUN apk add stress-ng
ENTRYPOINT [ "stress-ng", "-c", "1", "-q" ]
