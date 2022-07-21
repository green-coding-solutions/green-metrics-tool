#!/bin/bash
echo "Stopping docker containers..."
docker compose -f ../docker/test-compose.yml down