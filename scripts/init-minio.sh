#!/bin/bash

# MinIO initialization script for DuckLake
# This script creates the necessary buckets for DuckLake data storage

set -e

echo "🚀 Initializing MinIO for DuckLake..."

# Wait for MinIO to be ready
echo "⏳ Waiting for MinIO to be ready..."
until curl -f http://minio:9000/minio/health/live > /dev/null 2>&1; do
    echo "Waiting for MinIO..."
    sleep 2
done

echo "✅ MinIO is ready!"

# Configure MinIO client
mc alias set minio http://minio:9000 minioadmin minioadmin

# Create buckets for DuckLake
echo "📦 Creating DuckLake buckets..."

# Create main DuckLake data bucket
if ! mc ls minio/ducklake-data > /dev/null 2>&1; then
    mc mb minio/ducklake-data
    echo "✅ Created bucket: ducklake-data"
else
    echo "ℹ️  Bucket ducklake-data already exists"
fi

# Create bucket for legacy blockchain data (if needed)
if ! mc ls minio/blockchain-data > /dev/null 2>&1; then
    mc mb minio/blockchain-data
    echo "✅ Created bucket: blockchain-data"
else
    echo "ℹ️  Bucket blockchain-data already exists"
fi

# Set bucket policies (optional - for development)
echo "🔐 Setting bucket policies..."

# Allow read/write access to DuckLake bucket
mc anonymous set download minio/ducklake-data
mc anonymous set upload minio/ducklake-data

echo "🎉 MinIO initialization complete!"
echo ""
echo "📊 Bucket summary:"
mc ls minio/
echo ""
echo "🔗 MinIO Console: http://localhost:9001"
echo "   Username: minioadmin"
echo "   Password: minioadmin"
