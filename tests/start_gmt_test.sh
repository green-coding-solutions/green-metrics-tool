#!/bin/bash

echo "Starting Green Metrics Tool environment..."

# In Projektordner wechseln
cd ~/gmt-fresh || exit

echo "Starting infrastructure containers..."
docker compose up -d

echo "Waiting for containers to be ready..."
sleep 5

echo "Checking running containers..."
docker ps

echo "Starting test run..."

source venv/bin/activate

python runner.py \
  --uri /home/jahns/gmt-fresh \
  --name CPU_RAM_Test \
  --filename tests/usage_the_test.yml \
  --variable "__GMT_VAR_CPU_DURATION__=20" \
  --variable "__GMT_VAR_RAM_MB__=256" \
  --variable "__GMT_VAR_RAM_DURATION__=20"

echo "Test started."

echo "Showing metric logs..."
tail -f /tmp/green-metrics-tool/metrics/*
