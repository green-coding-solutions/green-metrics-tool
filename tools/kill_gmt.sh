#!/usr/bin/env bash

read -p "This will kill all processes know to be forked by GMT. It may also kill other similar named processes and should only be used on dedicated measurement nodes. In case you are looged in remotely it will also kill the current terminal session, so you must log in again. Do you want to continue? (y/N) : " kill_gmt

if [[  "$kill_gmt" == "Y" || "$kill_gmt" == "y" ]] ; then
    pgrep python3 | xargs kill
    pgrep tinyproxy | xargs kill
    pgrep -f metric_providers | xargs kill
    pgrep tcpdump | xargs kill
    docker rm -f $(docker ps -aq) 2>/dev/null
    pgrep bash | xargs kill -9
fi