#!/usr/bin/env bash
# ESG Report Creator - Test Runner
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "🧪 Running tests..."

# Parse arguments
RUN_BACKEND=true
RUN_FRONTEND=true
RUN_E2E=false
COVERAGE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --backend)
            RUN_BACKEND=true
            RUN_FRONTEND=false
            shift
            ;;
        --frontend)
            RUN_BACKEND=false
            RUN_FRONTEND=true
            shift
            ;;
        --e2e)
            RUN_E2E=true
            shift
            ;;
        --coverage)
            COVERAGE=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Backend tests
if [ "$RUN_BACKEND" = true ]; then
    echo ""
    echo "=== Backend Tests ==="
    cd apps/api
    
    if command -v pytest &> /dev/null; then
        if [ "$COVERAGE" = true ]; then
            pytest tests/ -v --cov=app --cov-report=html --cov-report=term-missing
        else
            pytest tests/ -v
        fi
    else
        echo "⚠️ pytest not installed. Install with: pip install pytest"
    fi
    cd "$PROJECT_ROOT"
fi

# Frontend tests
if [ "$RUN_FRONTEND" = true ]; then
    echo ""
    echo "=== Frontend Tests ==="
    cd apps/web
    
    if [ -d "node_modules" ]; then
        npm run test
    else
        echo "⚠️ node_modules not found. Run: npm install"
    fi
    cd "$PROJECT_ROOT"
fi

# E2E tests
if [ "$RUN_E2E" = true ]; then
    echo ""
    echo "=== E2E Tests ==="
    cd e2e
    
    if [ -d "node_modules" ]; then
        npx playwright test
    else
        echo "⚠️ Playwright not installed. Run: npm install"
    fi
    cd "$PROJECT_ROOT"
fi

echo ""
echo "✅ Tests complete!"







