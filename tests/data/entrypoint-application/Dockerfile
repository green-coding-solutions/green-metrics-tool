FROM alpine
RUN apk add stress-ng
ENTRYPOINT [ "stress-ng", "-c", "1", "-q" ]
