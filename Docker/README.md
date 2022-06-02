# Dockerfiles method

The Dockerfiles will provide you with a running setup of the working system with just a few commands.

It can technically be used in production, however it is designed to run on your local machine for testing purposes.

Therefore some IP configurations are hardcoded to 127.0.0.1.

If you do not want that please make these changes inside the container `green-coding-nginx-gunicorn-container` once built

`sudo sed -i "s/http:\/\/127\.0\.0\.1:8080/http://YOUR_URL_OR_IP_ESCAPED_HERE/" website/index.html`

`sudo sed -i "s/http:\/\/127\.0\.0\.1:8080/http://YOUR_URL_OR_IP_ESCAPED_HERE/" website/request.html`


## Setup

- create network: `docker network create green-coding-net`
- Build build both containers. Please use the same password indicated in the placeholder `XXXX` for both: 
- - `docker build . --tag green-coding-nginx-gunicorn -f Dockerfile-gunicorn-nginx --build-arg postgres_pw=XXXX`
- - `docker build . --tag green-coding-postgres -f Dockerfile-postgres --build-arg postgres_pw=XXXX`
- Run the containers in the following order: 
- - `docker run -d -p 5432:5432 --net green-coding-net --name green-coding-postgres-container green-coding-postgres`
- - `docker run  -d -p 8000:80 -p 8080:8080 --net green-coding-net --name green-coding-nginx-gunicorn-container green-coding-nginx-gunicorn`


**Important:** Apply --no-cache option to the build commands if you experience problems. That might help.

## Connecting to DB
You can now connect to the db directly on port 5432, which is exposed to your host system.

The database name is `green-coding`, user is `postgres`, and the password is what you have specified during the docker build command.

## Limitations
These Dockerfiles are not meant to be used in production. The reason for this is that the containers depend on each other and have to be started and stopped alltogether, and never on their own.
