FROM nestybox/ubuntu-noble-systemd-docker@sha256:8b1c4409fe89bc110e1e468767074fe4403ba6bb2d1b34881fec5df8b6c2f9c3

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN \
    apt-get update && \
    apt-get install -y curl git make gcc python3 python3-pip python3-venv sudo && \
    rm -rf /var/lib/apt/lists/*

ENV USER=root
USER root

WORKDIR /root

# ENTRYPOINT ['/sbin/init', '--log-level=err'] # is used from base image. Here just for clarity.