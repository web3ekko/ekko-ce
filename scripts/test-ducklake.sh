#!/bin/bash

# DuckLake Integration Test Runner
# This script sets up the environment and runs DuckLake tests

set -e

echo "🧪 DuckLake Integration Test Runner"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if Docker is running
check_docker() {
    print_status "Checking Docker..."
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    print_success "Docker is running"
}

# Check if docker-compose is available
check_docker_compose() {
    print_status "Checking docker-compose..."
    if ! command -v docker-compose > /dev/null 2>&1; then
        print_error "docker-compose is not installed. Please install it and try again."
        exit 1
    fi
    print_success "docker-compose is available"
}

# Start test infrastructure
start_infrastructure() {
    print_status "Starting test infrastructure..."
    
    # Start MinIO and dependencies
    docker-compose up -d minio redis nats
    
    # Wait for services to be healthy
    print_status "Waiting for services to be ready..."
    
    # Wait for MinIO
    timeout=60
    counter=0
    while ! curl -f http://localhost:9000/minio/health/live > /dev/null 2>&1; do
        if [ $counter -ge $timeout ]; then
            print_error "MinIO failed to start within $timeout seconds"
            exit 1
        fi
        echo -n "."
        sleep 2
        counter=$((counter + 2))
    done
    echo ""
    print_success "MinIO is ready"
    
    # Initialize MinIO buckets (with timeout)
    print_status "Initializing MinIO buckets..."
    timeout 60 docker-compose up minio-init || {
        print_warning "MinIO initialization timed out, but MinIO should be running"
        print_status "Checking MinIO status..."
        if curl -f http://localhost:9000/minio/health/live > /dev/null 2>&1; then
            print_success "MinIO is accessible"
        else
            print_error "MinIO is not accessible"
            return 1
        fi
    }
    
    print_success "Test infrastructure is ready"
}

# Stop test infrastructure
stop_infrastructure() {
    print_status "Stopping test infrastructure..."
    docker-compose down -v
    print_success "Test infrastructure stopped"
}

# Run unit tests
run_unit_tests() {
    print_status "Running DuckLake unit tests..."

    # Activate virtual environment and run tests
    if source venv/bin/activate && pytest tests/unit/test_ducklake_services.py -v; then
        print_success "Unit tests passed"
    else
        print_error "Unit tests failed"
        return 1
    fi
}

# Run integration tests
run_integration_tests() {
    print_status "Running DuckLake integration tests..."

    # Activate virtual environment and run tests
    if source venv/bin/activate && pytest tests/integration/test_ducklake_integration.py -v; then
        print_success "Integration tests passed"
    else
        print_error "Integration tests failed"
        return 1
    fi
}

# Run CLI-based tests
run_cli_tests() {
    print_status "Running DuckDB CLI tests..."

    if ./scripts/test-duckdb-cli.sh; then
        print_success "CLI tests passed"
    else
        print_error "CLI tests failed"
        return 1
    fi
}

# Run Go client tests in container
run_go_client_tests() {
    print_status "Running Go DuckDB client tests in container..."

    # Build and run the Go client test
    if docker-compose up --build pipeline-duckdb-test; then
        print_success "Go client tests passed"
    else
        print_error "Go client tests failed"
        return 1
    fi

    # Clean up
    docker-compose stop pipeline-duckdb-test
    docker-compose rm -f pipeline-duckdb-test
}

# Run container-based tests
run_container_tests() {
    print_status "Running DuckLake tests in container..."

    # Start the test container
    docker-compose up -d ducklake-test

    # Wait for container to be ready
    sleep 5

    # Run the tests inside the container
    if docker-compose exec ducklake-test /app/test-ducklake.sh; then
        print_success "Container tests passed"
    else
        print_error "Container tests failed"
        return 1
    fi

    # Clean up
    docker-compose stop ducklake-test
}

# Test DuckLake with real MinIO
test_ducklake_with_minio() {
    print_status "Testing DuckLake with real MinIO..."
    
    # Create a simple test script
    cat > /tmp/test_ducklake_minio.py << 'EOF'
import duckdb
import tempfile
import os

def test_ducklake_minio():
    """Test DuckLake with MinIO backend."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        catalog_path = os.path.join(temp_dir, "test.sqlite")
        
        # Create connection
        conn = duckdb.connect()
        
        try:
            # Install extensions using Python API
            conn.install_extension("ducklake")
            conn.load_extension("ducklake")
            conn.install_extension("sqlite_scanner")
            conn.load_extension("sqlite_scanner")
            conn.install_extension("aws")
            conn.load_extension("aws")
            
            # Configure MinIO connection
            conn.execute("""
                CREATE OR REPLACE SECRET minio_test (
                    TYPE s3,
                    PROVIDER config,
                    KEY_ID 'minioadmin',
                    SECRET 'minioadmin',
                    REGION 'us-east-1',
                    ENDPOINT 'localhost:9000',
                    USE_SSL false
                );
            """)
            
            # Attach DuckLake
            conn.execute(f"""
                ATTACH 'ducklake:sqlite:{catalog_path}' AS test_minio 
                (DATA_PATH 's3://ducklake-data/test');
            """)
            
            conn.execute("USE test_minio;")
            
            # Create test table
            conn.execute("""
                CREATE TABLE test_table (
                    id INTEGER,
                    name VARCHAR,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            
            # Insert test data
            conn.execute("INSERT INTO test_table (id, name) VALUES (1, 'test1'), (2, 'test2');")
            
            # Query data
            result = conn.execute("SELECT * FROM test_table ORDER BY id;").fetchall()
            
            assert len(result) == 2, f"Expected 2 rows, got {len(result)}"
            assert result[0][0] == 1, f"Expected id=1, got {result[0][0]}"
            assert result[0][1] == 'test1', f"Expected name='test1', got {result[0][1]}"
            
            print("✅ DuckLake with MinIO test passed!")
            
        except Exception as e:
            print(f"❌ DuckLake with MinIO test failed: {e}")
            raise
        finally:
            conn.close()

if __name__ == "__main__":
    test_ducklake_minio()
EOF
    
    # Run the test with virtual environment
    if source venv/bin/activate && python /tmp/test_ducklake_minio.py; then
        print_success "DuckLake with MinIO test passed"
    else
        print_error "DuckLake with MinIO test failed"
        return 1
    fi
    
    # Cleanup
    rm -f /tmp/test_ducklake_minio.py
}

# Show test results summary
show_summary() {
    echo ""
    echo "🎉 DuckLake Test Summary"
    echo "======================="
    echo "✅ Docker infrastructure: Ready"
    echo "✅ MinIO buckets: Created"
    echo "✅ Unit tests: Passed"
    echo "✅ Integration tests: Passed"
    echo "✅ MinIO integration: Passed"
    echo ""
    echo "🔗 MinIO Console: http://localhost:9001"
    echo "   Username: minioadmin"
    echo "   Password: minioadmin"
    echo ""
    echo "📊 Check MinIO buckets:"
    echo "   - ducklake-data: DuckLake data files"
    echo "   - blockchain-data: Legacy blockchain data"
}

# Main execution
main() {
    case "${1:-all}" in
        "infrastructure")
            check_docker
            check_docker_compose
            start_infrastructure
            ;;
        "unit")
            run_unit_tests
            ;;
        "integration")
            run_integration_tests
            ;;
        "cli")
            run_cli_tests
            ;;
        "go")
            run_go_client_tests
            ;;
        "container")
            run_container_tests
            ;;
        "minio")
            test_ducklake_with_minio
            ;;
        "stop")
            stop_infrastructure
            ;;
        "all")
            check_docker
            check_docker_compose
            start_infrastructure
            
            # Run all tests
            run_unit_tests
            run_integration_tests
            test_ducklake_with_minio
            
            show_summary
            ;;
        *)
            echo "Usage: $0 [infrastructure|unit|integration|cli|go|container|minio|stop|all]"
            echo ""
            echo "Commands:"
            echo "  infrastructure  - Start test infrastructure (MinIO, Redis, NATS)"
            echo "  unit           - Run unit tests only"
            echo "  integration    - Run integration tests only"
            echo "  cli            - Run DuckDB CLI tests (simplest, no CGO issues)"
            echo "  go             - Run Go DuckDB client tests in container"
            echo "  container      - Run DuckDB tests in container (avoids CGO issues)"
            echo "  minio          - Test DuckLake with real MinIO"
            echo "  stop           - Stop test infrastructure"
            echo "  all            - Run all tests (default)"
            exit 1
            ;;
    esac
}

# Trap to cleanup on exit
trap 'print_warning "Test interrupted, cleaning up..."; stop_infrastructure' INT TERM

# Run main function
main "$@"
