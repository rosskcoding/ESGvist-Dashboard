#!/usr/bin/env bash
# ESGvist Dashboard - Development Environment Startup
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "Starting ESGvist Dashboard development environment..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Start core services
echo "Starting services (Postgres, Redis)..."
docker compose -f infra/compose.yml up -d postgres redis

# Wait for services to be healthy
echo "Waiting for database to be ready..."
sleep 5

# Run migrations
echo "Running database migrations..."
docker compose -f infra/compose.yml run --rm api alembic upgrade head || {
    echo "Migrations failed. Starting services anyway..."
}

# Start API and Web
docker compose -f infra/compose.yml up -d api web

echo ""
echo "ESGvist Dashboard is ready!"
echo ""
echo "Services:"
echo "   API:      http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo "   Web:      http://localhost:5173"
echo "   Postgres: localhost:5432"
echo "   Redis:    localhost:6379"
echo ""
echo "Commands:"
echo "   View logs:    docker compose -f infra/compose.yml logs -f"
echo "   Stop all:     docker compose -f infra/compose.yml down"
echo "   Run tests:    docker compose -f infra/compose.yml --profile test run --rm api-tests"
