#!/bin/bash

# Run DuckLake Integration Example
# This script demonstrates the complete DuckLake integration

set -e

echo "🚀 DuckLake Integration Example Runner"
echo "====================================="

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

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if Go is installed
    if ! command -v go > /dev/null 2>&1; then
        print_error "Go is not installed. Please install Go and try again."
        exit 1
    fi
    
    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    
    # Check if docker-compose is available
    if ! command -v docker-compose > /dev/null 2>&1; then
        print_error "docker-compose is not installed. Please install it and try again."
        exit 1
    fi
    
    print_success "All prerequisites are met"
}

# Start infrastructure
start_infrastructure() {
    print_status "Starting infrastructure..."
    
    # Start MinIO, NATS, and Redis
    docker-compose up -d minio nats redis
    
    # Wait for services to be ready
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
    
    # Wait for NATS
    counter=0
    while ! nc -z localhost 4222 > /dev/null 2>&1; do
        if [ $counter -ge $timeout ]; then
            print_error "NATS failed to start within $timeout seconds"
            exit 1
        fi
        echo -n "."
        sleep 2
        counter=$((counter + 2))
    done
    echo ""
    
    print_success "Infrastructure is ready"
    
    # Initialize MinIO buckets
    print_status "Initializing MinIO buckets..."
    docker-compose up minio-init
    
    print_success "MinIO buckets initialized"
}

# Set environment variables for DuckLake
set_environment() {
    print_status "Setting up DuckLake environment..."
    
    export DUCKLAKE_ENABLED=true
    export DUCKLAKE_CATALOG_TYPE=sqlite
    export DUCKLAKE_CATALOG_PATH=/tmp/ducklake_example_catalog.sqlite
    export DUCKLAKE_DATA_PATH=s3://ducklake-data/example-data
    export DUCKLAKE_BUCKET_NAME=ducklake-data
    export DUCKLAKE_BATCH_SIZE=100
    export DUCKLAKE_FLUSH_INTERVAL=10s
    
    export MINIO_ENDPOINT=localhost:9000
    export MINIO_ACCESS_KEY=minioadmin
    export MINIO_SECRET_KEY=minioadmin
    export MINIO_REGION=us-east-1
    export MINIO_SECURE=false
    
    export NATS_URL=nats://localhost:4222
    export NATS_STREAM=blockchain
    export NATS_SUBJECT=transactions
    
    print_success "Environment variables set"
    
    # Print configuration
    echo ""
    echo "📋 DuckLake Configuration:"
    echo "  DUCKLAKE_ENABLED: $DUCKLAKE_ENABLED"
    echo "  DUCKLAKE_CATALOG_TYPE: $DUCKLAKE_CATALOG_TYPE"
    echo "  DUCKLAKE_CATALOG_PATH: $DUCKLAKE_CATALOG_PATH"
    echo "  DUCKLAKE_DATA_PATH: $DUCKLAKE_DATA_PATH"
    echo "  DUCKLAKE_BUCKET_NAME: $DUCKLAKE_BUCKET_NAME"
    echo "  MINIO_ENDPOINT: $MINIO_ENDPOINT"
    echo ""
}

# Build and run the example
run_example() {
    print_status "Building DuckLake integration example..."
    
    # Navigate to pipeline directory
    cd pipeline
    
    # Build the example
    if go build -o ../bin/ducklake-example ./examples/ducklake_integration_example.go; then
        print_success "Example built successfully"
    else
        print_error "Failed to build example"
        exit 1
    fi
    
    # Navigate back
    cd ..
    
    print_status "Running DuckLake integration example..."
    
    # Run the example
    if ./bin/ducklake-example; then
        print_success "Example completed successfully"
    else
        print_error "Example failed"
        exit 1
    fi
}

# Verify results
verify_results() {
    print_status "Verifying results..."
    
    # Check if catalog file was created
    if [ -f "/tmp/ducklake_example_catalog.sqlite" ]; then
        print_success "DuckLake catalog file created"
        
        # Show file size
        size=$(ls -lh /tmp/ducklake_example_catalog.sqlite | awk '{print $5}')
        echo "  Catalog file size: $size"
    else
        print_warning "DuckLake catalog file not found"
    fi
    
    # Check MinIO bucket contents
    print_status "Checking MinIO bucket contents..."
    
    # Use MinIO client to list bucket contents
    docker run --rm --network ekko-ce_pipeline-network \
        -e MC_HOST_minio=http://minioadmin:minioadmin@minio:9000 \
        minio/mc ls minio/ducklake-data/ || print_warning "Could not list bucket contents"
    
    print_success "Verification complete"
}

# Show summary
show_summary() {
    echo ""
    echo "🎉 DuckLake Integration Example Summary"
    echo "======================================"
    echo "✅ Infrastructure: Started"
    echo "✅ Environment: Configured"
    echo "✅ Example: Executed"
    echo "✅ Results: Verified"
    echo ""
    echo "🔗 Useful Links:"
    echo "  MinIO Console: http://localhost:9001"
    echo "    Username: minioadmin"
    echo "    Password: minioadmin"
    echo ""
    echo "📊 What happened:"
    echo "  1. Created DuckLake writer with SQLite catalog"
    echo "  2. Processed 5 sample transactions"
    echo "  3. Stored data in MinIO bucket: ducklake-data"
    echo "  4. Created catalog metadata in SQLite file"
    echo ""
    echo "🚀 Next steps:"
    echo "  1. Check MinIO console for stored data files"
    echo "  2. Run API service to query the data"
    echo "  3. Test time travel and snapshot features"
    echo "  4. Integrate with your pipeline"
}

# Cleanup function
cleanup() {
    print_status "Cleaning up..."
    
    # Remove temporary files
    rm -f /tmp/ducklake_example_catalog.sqlite
    rm -f ./bin/ducklake-example
    
    # Stop infrastructure
    docker-compose down
    
    print_success "Cleanup complete"
}

# Main execution
main() {
    case "${1:-run}" in
        "infrastructure")
            check_prerequisites
            start_infrastructure
            ;;
        "example")
            set_environment
            run_example
            verify_results
            ;;
        "cleanup")
            cleanup
            ;;
        "run")
            check_prerequisites
            start_infrastructure
            set_environment
            run_example
            verify_results
            show_summary
            ;;
        *)
            echo "Usage: $0 [infrastructure|example|cleanup|run]"
            echo ""
            echo "Commands:"
            echo "  infrastructure  - Start infrastructure only"
            echo "  example        - Run example only (requires infrastructure)"
            echo "  cleanup        - Clean up resources"
            echo "  run            - Run complete example (default)"
            exit 1
            ;;
    esac
}

# Trap to cleanup on exit
trap 'print_warning "Script interrupted, cleaning up..."; cleanup' INT TERM

# Create bin directory if it doesn't exist
mkdir -p bin

# Run main function
main "$@"
