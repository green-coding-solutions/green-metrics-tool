# Dockerfiles method

The Dockerfiles will provide you with a running setup of the working system with just a few commands.

It can be used in production, is however technically designed to run on your local machine for testing purposes.

Therefore some IP configurations are hardcoded to 127.0.0.1.

If you do not want that please make these changes inside the container `green-coding-nginx-gunicorn-container` once built

`sudo sed -i "s/http:\/\/127\.0\.0\.1:8080/http://YOUR_URL_OR_IP_ESCAPED_HERE/" cron/send_email.py`

`sudo sed -i "s/http:\/\/127\.0\.0\.1:8080/http://YOUR_URL_OR_IP_ESCAPED_HERE/" website/index.html`

`sudo sed -i "s/http:\/\/127\.0\.0\.1:8080/http://YOUR_URL_OR_IP_ESCAPED_HERE/" website/request.html`


## Setup

- create network: `docker network create green-coding-net`
Build with: `docker build . --tag green-coding-nginx-gunicorn -f Dockerfile-gunicorn-nginx --build-arg postgres_pw=XXXX`
- - Please use a password here for XXXX
- Run with: `docker run  -d -p 8000:80 -p 8080:8080 --net green-coding-net --name green-coding-nginx-gunicorn-container green-coding-nginx-gunicorn`
- Build next container with: `docker build . --tag green-coding-postgres -f Dockerfile-postgres --build-arg postgres_pw=XXXX`
- - Please use the same password here
- Run with: `docker run -d -p 5432:5432 --net green-coding-net --name green-coding-postgres-container green-coding-postgres`


Important: Apply --no-cache option to the build commands if you experience problems. That might help.