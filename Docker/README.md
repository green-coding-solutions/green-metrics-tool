# Dockerfiles method

The Dockerfiles will provide you with a running setup of the working system with just a few commands.

It can technically be used in production, however it is designed to run on your local machine for testing purposes.

The system binds in your host OS to port 8000. So it will be accessible through `http://metrics.green-coding.local:8000`

Please set an entry in your `/etc/hosts` file accordingly like so:

`127.0.0.1 api.green-coding.local metrics.green-coding.local`


## Setup

- create network: `docker network create green-coding-net`
- Build build both containers. Please use the same password indicated in the placeholder `XXXX` for both: 
- - `docker build . --tag green-coding-nginx-gunicorn -f Dockerfile-gunicorn-nginx --build-arg postgres_pw=XXXX`
- - `docker build . --tag green-coding-postgres -f Dockerfile-postgres --build-arg postgres_pw=XXXX`
- Run the containers in the following order: 
- - `docker run -d -p 5432:5432 --net green-coding-net --name green-coding-postgres-container green-coding-postgres`
- - `docker run  -d -p 8000:80 --net green-coding-net --name green-coding-nginx-gunicorn-container green-coding-nginx-gunicorn`


**Important:** Apply --no-cache option to the build commands if you experience problems. That might help.

## Connecting to DB
You can now connect to the db directly on port 5432, which is exposed to your host system.\
The expose to the host system is not needed. If you do not want to access the db directly just remove the `-p 5432:5432` option.

The database name is `green-coding`, user is `postgres`, and the password is what you have specified during the docker build command.

## Limitations
These Dockerfiles are not meant to be used in production. The reason for this is that the containers depend on each other and have to be started and stopped alltogether, and never on their own.
