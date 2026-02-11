#!/bin/bash
# Rebuild and start local development environment (Mac/Linux)

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    echo "Error: .env file not found. Copy .env.example to .env and add your secrets."
    exit 1
fi

echo "Rebuilding and starting local development environment..."
docker-compose -f docker-compose.local.yml up --build -d

echo ""
echo "Services starting:"
echo "  - Frontend:  http://localhost:3000"
echo "  - API:       http://localhost:8080"
echo "  - MinIO:     http://localhost:9001"
echo ""
echo "Use 'docker-compose -f docker-compose.local.yml logs -f' to view logs"
