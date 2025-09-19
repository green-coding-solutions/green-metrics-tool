FROM alpine

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy

RUN apk add stress-ng

COPY . /tmp/
COPY ./subdir/subdir2/subdir3/testfile3 /tmp/testfile3-correctly-copied
COPY ./testfile-root /tmp/testfile-root-extra-copied

CMD ["sh"]