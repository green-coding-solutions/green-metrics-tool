# Prebuilt GMT postgres image

`greencoding/gmt-postgres` is the official `postgres:18` image with the GMT schema and seed data baked in.
It replaces the `green-coding-postgres` service from a regular install, which mounts the same SQL files from a clone of the repository.

## Tags

The tags are the same as for [`greencoding/gmt-frontend`](../frontend-image/README.md#tags). Use the same tag for both images and for the API.

## Usage

```yaml
services:
  green-coding-postgres:
    image: greencoding/gmt-postgres:latest
    container_name: green-coding-postgres-container
    restart: always
    shm_size: 256MB
    environment:
      - POSTGRES_PASSWORD=PLEASE_CHANGE_THIS
      - TZ=Europe/Berlin
    volumes:
      - green-coding-postgres-data:/var/lib/postgresql
    ports:
      - 9573:9573

volumes:
  green-coding-postgres-data:
```

- `POSTGRES_PASSWORD` is required. Use the same password as `postgresql.password` in the `config.yml` of the API and the runner.
- The database is called `green-coding` and listens on port `9573` with SSL on, as the API and the runner connect with `sslmode=require`.
- `TZ` sets the time zone of the database when it is created.
- The server starts with `shared_buffers=1.2GB`, like a regular install. On a smaller host, override `command` with the flags from the [Dockerfile](Dockerfile) and a lower value.

## Schema setup and updates

The schema and seed data are only created on the first start, when the data volume is empty. Later starts and newer images do not touch an existing database.

To update an existing database to a newer image, apply the new files from [`migrations/`](../../migrations/) with `psql` before you start the newer API, the same as for a regular install.

The seed data contains the default users of a regular install, including user 1 with the token `DEFAULT`. Change or remove it if the database is reachable from outside.

## Building and testing locally

From the repository root:

```bash
docker build -f docker/postgres-image/Dockerfile -t gmt-postgres:test .
./docker/postgres-image/test-image.sh gmt-postgres:test
```
