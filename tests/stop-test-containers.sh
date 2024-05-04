#!/bin/bash
set -euo pipefail

echo "Stopping docker containers..."
docker compose -f ../docker/test-compose.yml down -v --remove-orphans