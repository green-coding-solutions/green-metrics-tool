#!/usr/bin/env bash

set -euo pipefail

echo "This script works only locally as it imports into the docker container directly!"

read -p "You are about to drop all data in the current database and import from a backup! Sure? (y/N) : " response
if [[  "$response" == "Y" || "$response" == "y" ]] ; then

    docker exec green-coding-postgres-container psql -v ON_ERROR_STOP=1 -Upostgres -p9573 -dgreen-coding -c 'DROP schema IF EXISTS "public" CASCADE;'
    docker exec green-coding-postgres-container psql -v ON_ERROR_STOP=1 -Upostgres -p9573 -dgreen-coding -c 'CREATE SCHEMA IF NOT EXISTS "public";'
    docker exec green-coding-postgres-container psql -v ON_ERROR_STOP=1 -Upostgres -p9573 -dgreen-coding -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp" SCHEMA public;'
    docker exec green-coding-postgres-container psql -v ON_ERROR_STOP=1 -Upostgres -p9573 -dgreen-coding -c 'CREATE EXTENSION IF NOT EXISTS "moddatetime" SCHEMA public;'

    read -p "Please put all files you want to import now in the subfolder ./backup. Then press enter: " response

    cat ./backup/* | docker exec -i green-coding-postgres-container psql -v ON_ERROR_STOP=1 -Upostgres -p9573 -dgreen-coding
fi