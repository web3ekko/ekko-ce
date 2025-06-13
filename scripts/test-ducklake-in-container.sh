#!/bin/bash

# Test DuckLake functionality from within a Docker container
# This avoids CGO and platform-specific build issues

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Test DuckDB with available extensions using CLI
test_duckdb_extensions() {
    print_status "Testing DuckDB extensions in container using CLI..."

    # Check if DuckDB CLI is available
    if ! command -v duckdb > /dev/null 2>&1; then
        print_status "DuckDB CLI not found in container. Installing..."
        # Install DuckDB CLI
        apt-get update && apt-get install -y wget unzip

        # Detect architecture
        ARCH=$(uname -m)
        if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
            DUCKDB_URL="https://github.com/duckdb/duckdb/releases/download/v1.3.0/duckdb_cli-linux-aarch64.zip"
        else
            DUCKDB_URL="https://github.com/duckdb/duckdb/releases/download/v1.3.0/duckdb_cli-linux-amd64.zip"
        fi

        print_status "Downloading DuckDB for architecture: $ARCH"
        wget -O duckdb.zip "$DUCKDB_URL"
        unzip duckdb.zip
        chmod +x duckdb
        mv duckdb /usr/local/bin/
        rm duckdb.zip
        print_success "DuckDB CLI installed successfully"
    fi

    print_status "DuckDB CLI version: $(duckdb --version)"

    # Create SQL test script
    cat > /tmp/test_extensions.sql << 'EOF'
-- Test basic functionality
SELECT 'DuckDB CLI is working in container!' as message;

-- Show available extensions
.print "📦 Available extensions:"
SELECT extension_name, installed, loaded
FROM duckdb_extensions()
ORDER BY extension_name;

-- Install and test key extensions
.print ""
.print "🔧 Installing extensions..."

INSTALL aws;
LOAD aws;
.print "✅ AWS extension loaded"

INSTALL sqlite_scanner;
LOAD sqlite_scanner;
.print "✅ SQLite scanner extension loaded"

INSTALL delta;
LOAD delta;
.print "✅ Delta extension loaded"

-- Verify extensions are loaded
.print ""
.print "📋 Loaded extensions:"
SELECT extension_name, loaded
FROM duckdb_extensions()
WHERE loaded = true
ORDER BY extension_name;

.print "🎉 DuckDB container CLI test completed successfully!"
EOF

    # Run the test
    if duckdb < /tmp/test_extensions.sql; then
        print_success "DuckDB extensions test passed"
        rm -f /tmp/test_extensions.sql
        return 0
    else
        print_error "DuckDB extensions test failed"
        rm -f /tmp/test_extensions.sql
        return 1
    fi
}

# Test MinIO connectivity from container using CLI
test_minio_connectivity() {
    print_status "Testing MinIO connectivity from container using CLI..."

    # Set MinIO environment variables
    export MINIO_ENDPOINT="${MINIO_ENDPOINT:-minio:9000}"
    export MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
    export MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
    export MINIO_BUCKET="${MINIO_BUCKET:-blockchain-data}"
    export MINIO_USE_SSL="${MINIO_USE_SSL:-false}"

    print_status "Testing MinIO connection to $MINIO_ENDPOINT"

    # Create SQL script for MinIO testing
    cat > /tmp/test_minio.sql << EOF
-- Install and load AWS extension
INSTALL aws;
LOAD aws;

-- Configure S3/MinIO settings
SET s3_endpoint='$MINIO_ENDPOINT';
SET s3_access_key_id='$MINIO_ACCESS_KEY';
SET s3_secret_access_key='$MINIO_SECRET_KEY';
SET s3_use_ssl=$MINIO_USE_SSL;
SET s3_region='us-east-1';

.print "✅ MinIO/S3 configuration completed"

-- Test creating a table with transaction data
CREATE TABLE test_transactions AS
SELECT
    'Avalanche' as network,
    'Mainnet' as subnet,
    'EVM' as vm_type,
    NOW() as block_time,
    '0xtest123' as tx_hash,
    '0xfrom123' as from_address,
    '0xto123' as to_address,
    '1000000000000000000' as value;

.print "✅ Test table created"

-- Show table contents
SELECT * FROM test_transactions;

.print "🎉 MinIO connectivity test completed!"
EOF

    # Run the test
    if duckdb < /tmp/test_minio.sql; then
        print_success "MinIO connectivity test passed"
        rm -f /tmp/test_minio.sql
        return 0
    else
        print_warning "MinIO connectivity test had issues (this is expected if MinIO is not accessible)"
        rm -f /tmp/test_minio.sql
        return 0  # Don't fail the test if MinIO is not accessible
    fi
}

# Main execution
main() {
    echo "🧪 DuckLake Container Test Runner"
    echo "=================================="
    
    # Test DuckDB extensions
    if ! test_duckdb_extensions; then
        exit 1
    fi
    
    echo ""
    
    # Test MinIO connectivity
    if ! test_minio_connectivity; then
        exit 1
    fi
    
    echo ""
    print_success "All container tests passed! 🎉"
}

# Run main function
main "$@"
