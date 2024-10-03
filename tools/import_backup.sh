#!/bin/bash

set -euo pipefail

echo "This script works only locally as it imports into the docker container directly!"

read -p "You are about to drop all data in the current database and import from a backup! Sure? (y/N) : " response
if [[  "$response" == "Y" || "$response" == "y" ]] ; then

    docker exec green-coding-postgres-container psql -Upostgres -p9573 -dgreen-coding -c 'DROP schema IF EXISTS "public" CASCADE;'
    docker exec green-coding-postgres-container psql -Upostgres -p9573 -dgreen-coding -c 'CREATE SCHEMA IF NOT EXISTS "public";'
    docker exec green-coding-postgres-container psql -Upostgres -p9573 -dgreen-coding -c 'CREATE EXTENSION "uuid-ossp";'
    docker exec green-coding-postgres-container psql -Upostgres -p9573 -dgreen-coding -c 'CREATE EXTENSION "moddatetime";'

    read -p "Please put all files you want to import now in the subfolder ./backup. Then press enter: " response

    cat ./backup/* | docker exec -i green-coding-postgres-container psql -Upostgres -p9573 -dgreen-coding
fi