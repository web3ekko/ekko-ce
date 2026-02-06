#!/bin/bash

# Test runner script for Django API
# Supports different test categories and configurations

set -e

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TEST_TYPE="all"
COVERAGE=true
PARALLEL=false
VERBOSE=false
INTEGRATION=true

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -t, --type TYPE        Test type: all, unit, integration, models, serializers, views, services"
    echo "  -c, --no-coverage      Disable coverage reporting"
    echo "  -p, --parallel         Run tests in parallel"
    echo "  -v, --verbose          Verbose output"
    echo "  -i, --no-integration   Skip integration tests"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                     # Run all tests with coverage"
    echo "  $0 -t unit             # Run only unit tests"
    echo "  $0 -t models -v        # Run model tests with verbose output"
    echo "  $0 -p -c               # Run all tests in parallel without coverage"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--type)
            TEST_TYPE="$2"
            shift 2
            ;;
        -c|--no-coverage)
            COVERAGE=false
            shift
            ;;
        -p|--parallel)
            PARALLEL=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -i|--no-integration)
            INTEGRATION=false
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    print_error "pytest is not installed. Please install test requirements:"
    echo "pip install -r requirements-test.txt"
    exit 1
fi

# Build pytest command
PYTEST_CMD="pytest"
TEST_PATHS=""
MARKER_EXPR=""

# Add test path based on type
case $TEST_TYPE in
    "all")
        TEST_PATHS="app/tests tests"
        ;;
    "unit")
        TEST_PATHS="app/tests/test_models app/tests/test_serializers app/tests/test_views app/tests/test_services tests/unit"
        MARKER_EXPR="not integration"
        ;;
    "integration")
        TEST_PATHS="app/tests/test_integration tests/integration"
        MARKER_EXPR="integration"
        ;;
    "models")
        TEST_PATHS="app/tests/test_models tests/unit/models"
        MARKER_EXPR="models"
        ;;
    "serializers")
        TEST_PATHS="app/tests/test_serializers"
        MARKER_EXPR="serializers"
        ;;
    "views")
        TEST_PATHS="app/tests/test_views tests/unit/api"
        MARKER_EXPR="views"
        ;;
    "services")
        TEST_PATHS="app/tests/test_services tests/unit/services"
        MARKER_EXPR="services"
        ;;
    *)
        print_error "Invalid test type: $TEST_TYPE"
        show_usage
        exit 1
        ;;
esac

# Add test paths
if [ -n "$TEST_PATHS" ]; then
    PYTEST_CMD="$PYTEST_CMD $TEST_PATHS"
fi

# Skip integration tests if requested and no marker was set
if [ "$INTEGRATION" = false ] && [ -z "$MARKER_EXPR" ]; then
    MARKER_EXPR="not integration"
fi

# Add coverage options
if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=app --cov-report=html --cov-report=term-missing"
else
    PYTEST_CMD="$PYTEST_CMD --no-cov"
fi

# Add parallel execution
if [ "$PARALLEL" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -n auto"
fi

# Add verbose output
if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

# Add marker expression if provided
if [ -n "$MARKER_EXPR" ]; then
    PYTEST_CMD="$PYTEST_CMD -m \"$MARKER_EXPR\""
fi

# Print test configuration
print_status "Running Django API tests..."
print_status "Test type: $TEST_TYPE"
print_status "Coverage: $COVERAGE"
print_status "Parallel: $PARALLEL"
print_status "Verbose: $VERBOSE"
print_status "Integration: $INTEGRATION"
echo ""

# Set Django settings for testing
export DJANGO_SETTINGS_MODULE=ekko_api.settings.test

# Ensure we run from the API directory
cd "$SCRIPT_DIR"

STARTED_CONTAINERS=false
if [ "$INTEGRATION" = true ]; then
    if [ -f "$COMPOSE_FILE" ]; then
        if command -v docker-compose &> /dev/null; then
            running_count=0
            for container in ekko-postgres-dev ekko-redis-dev ekko-nats-dev; do
                if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
                    running_count=$((running_count + 1))
                fi
            done

            if [ "$running_count" -lt 3 ]; then
                print_status "Starting test containers..."
                docker-compose -f "$COMPOSE_FILE" up -d postgres redis nats

                if [ "$running_count" -eq 0 ]; then
                    STARTED_CONTAINERS=true
                fi

                # Wait for services to be ready
                print_status "Waiting for services to be ready..."
                sleep 10
            else
                print_status "Test containers already running"
            fi
        else
            print_warning "docker-compose not found; skipping container startup"
        fi
    else
        print_warning "docker-compose.yml not found at $COMPOSE_FILE; skipping container startup"
    fi
fi

# Run database migrations for testing
print_status "Setting up test database..."
python manage.py migrate --settings=ekko_api.settings.test --run-syncdb

# Run the tests
print_status "Executing tests..."
echo "Command: $PYTEST_CMD"
echo ""

if eval $PYTEST_CMD; then
    print_success "All tests passed!"
    
    # Show coverage report location if coverage was enabled
    if [ "$COVERAGE" = true ]; then
        print_status "Coverage report generated at: htmlcov/index.html"
    fi
    
    exit_code=0
else
    print_error "Some tests failed!"
    exit_code=1
fi

# Clean up test containers
if [ "$STARTED_CONTAINERS" = true ]; then
    print_status "Cleaning up test containers..."
    docker-compose -f "$COMPOSE_FILE" down
fi

exit $exit_code
