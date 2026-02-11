#!/bin/bash
# Stop local development environment (Mac/Linux)

cd "$(dirname "$0")/.."

echo "Stopping local development environment..."
docker-compose -f docker-compose.local.yml down

echo "Done."
