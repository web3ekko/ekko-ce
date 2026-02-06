#!/bin/sh
set -e

echo "Waiting for MinIO to be ready..."

# Retry loop for MinIO availability (max 30 attempts, 1s interval)
RETRY=0
MAX_RETRY=30

until /usr/bin/mc alias set myminio http://minio:9000 "${MINIO_ROOT_USER:-minioadmin}" "${MINIO_ROOT_PASSWORD:-minioadmin123}" 2>/dev/null; do
  RETRY=$((RETRY+1))
  if [ "$RETRY" -ge "$MAX_RETRY" ]; then
    echo "ERROR: MinIO not ready after 30 attempts"
    exit 1
  fi
  echo "Attempt $RETRY/$MAX_RETRY: MinIO not ready, waiting..."
  sleep 1
done

echo "MinIO is ready, creating buckets..."

# Create ekko-ducklake bucket
if /usr/bin/mc mb myminio/ekko-ducklake 2>/dev/null || /usr/bin/mc ls myminio/ekko-ducklake >/dev/null 2>&1; then
  echo "Bucket ekko-ducklake created or already exists"
else
  echo "ERROR: Failed to create ekko-ducklake bucket"
  exit 1
fi

# Set bucket policies (using anonymous command for newer mc versions)
/usr/bin/mc anonymous set public myminio/ekko-ducklake || /usr/bin/mc policy set public myminio/ekko-ducklake

# Verify buckets exist (without grep - not available in mc image)
echo "Verifying bucket creation..."
if /usr/bin/mc ls myminio/ekko-ducklake >/dev/null 2>&1; then
  echo "SUCCESS: Bucket ekko-ducklake verified"
else
  echo "ERROR: Bucket ekko-ducklake not found after creation"
  exit 1
fi

echo "All buckets created and verified successfully"
exit 0
