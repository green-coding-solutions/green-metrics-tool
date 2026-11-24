# Prebuilt GMT database: the official postgres image with the GMT schema and seed data
#
# Build from the repository root, as the image needs the SQL files from docker/:
#   docker build -f docker/postgres-image/Dockerfile -t greencoding/gmt-postgres .
#
# Usage is described in docker/postgres-image/README.md
FROM postgres:18

# Same as the green-coding-postgres service in docker/compose.yml.example
ENV POSTGRES_DB=green-coding \
    PGOPTIONS="-c search_path=public"

# The postgres entrypoint runs these only on the first start, when the data volume is empty.
# Existing databases are updated with the files in migrations/ instead.
COPY docker/structure.sql /docker-entrypoint-initdb.d/01-structure.sql
COPY docker/tables.sql /docker-entrypoint-initdb.d/02-tables.sql
COPY docker/seed-data.sql /docker-entrypoint-initdb.d/04-seed-data.sql

EXPOSE 9573

# Same server settings as docker/compose.yml.example. The API and the runner connect with
# sslmode=require, so SSL must stay on. Override the command to tune memory for your host.
CMD ["postgres", \
     "-c", "ssl=on", \
     "-c", "ssl_cert_file=/etc/ssl/certs/ssl-cert-snakeoil.pem", \
     "-c", "ssl_key_file=/etc/ssl/private/ssl-cert-snakeoil.key", \
     "-c", "shared_buffers=1.2GB", \
     "-c", "work_mem=32MB", \
     "-c", "maintenance_work_mem=1GB", \
     "-p", "9573"]
