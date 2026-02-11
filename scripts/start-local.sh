#!/bin/bash
# Start local development environment (Mac/Linux)

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    echo "Error: .env file not found. Copy .env.example to .env and add your secrets."
    exit 1
fi

echo "Starting local development environment..."
docker-compose -f docker-compose.local.yml up -d

echo ""
echo "Services starting:"
echo "  - Frontend/API: http://localhost:8080"
echo ""
echo "Use 'docker-compose -f docker-compose.local.yml logs -f' to view logs"
