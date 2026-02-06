#!/bin/bash
set -e

# Generate WADM manifest from template
# This script substitutes environment variables into the manifest template

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_FILE="${SCRIPT_DIR}/manifests/ekko-actors.template.yaml"
OUTPUT_FILE="${OUTPUT_FILE:-${SCRIPT_DIR}/manifests/ekko-actors-generated.yaml}"

# Environment-specific defaults
ENVIRONMENT="${ENVIRONMENT:-development}"
MANIFEST_VERSION="${MANIFEST_VERSION:-v1.0.0}"
ACTOR_REGISTRY="${ACTOR_REGISTRY:-localhost:5001}"
ACTOR_TAG="${ACTOR_TAG:-v1.0.0}"
NAMESPACE="${NAMESPACE:-ekko}"

# Custom provider version (defaults to ACTOR_TAG if not set)
# Note: newheads-evm provider v1.0.3+ is required (uses Unix signals instead of stdin)
PROVIDER_TAG="${PROVIDER_TAG:-${ACTOR_TAG}}"
PROVIDER_REGISTRY="${PROVIDER_REGISTRY:-${ACTOR_REGISTRY}}"
DUCKLAKE_WRITE_TAG="${DUCKLAKE_WRITE_TAG:-${PROVIDER_TAG}}"
ETH_TRANSFERS_PROCESSOR_TAG="${ETH_TRANSFERS_PROCESSOR_TAG:-${ACTOR_TAG}}"
NOTIFICATION_ROUTER_TAG="${NOTIFICATION_ROUTER_TAG:-${ACTOR_TAG}}"

# Provider configuration URLs (Kubernetes service names)
REDIS_URL="${REDIS_URL:-redis://:redis123@redis-master.${NAMESPACE}.svc.cluster.local:6379}"
NATS_URL="${NATS_URL:-nats://nats-headless.${NAMESPACE}.svc.cluster.local:4222}"
RESEND_API_KEY="${RESEND_API_KEY:-}"
TELEGRAM_WEBHOOK_PORT="${TELEGRAM_WEBHOOK_PORT:-8081}"
NEWHEADS_ENABLED="${NEWHEADS_ENABLED:-false}"

# S3/MinIO configuration
# For development, MinIO runs on host via docker-compose (ekko-minio-dev)
# From inside K8s, use host.docker.internal to reach host services
S3_ENDPOINT="${S3_ENDPOINT:-http://host.docker.internal:9000}"
S3_BUCKET="${S3_BUCKET:-ekko-ducklake}"
S3_ACCESS_KEY_ID="${S3_ACCESS_KEY_ID:-minioadmin}"
S3_SECRET_ACCESS_KEY="${S3_SECRET_ACCESS_KEY:-minioadmin123}"

# PostgreSQL configuration (DuckLake metadata catalog)
POSTGRES_HOST="${POSTGRES_HOST:-postgresql.${NAMESPACE}.svc.cluster.local}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-ekko}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-ekko123}"
DUCKLAKE_POSTGRES_DATABASE="${DUCKLAKE_POSTGRES_DATABASE:-${POSTGRES_DB:-ducklake_catalog}}"

# DuckLake write buffering (dev can reduce for faster E2E; prod can keep defaults)
DUCKLAKE_BUFFER_TIME_THRESHOLD_SECONDS="${DUCKLAKE_BUFFER_TIME_THRESHOLD_SECONDS:-30}"
DUCKLAKE_BUFFER_COUNT_THRESHOLD="${DUCKLAKE_BUFFER_COUNT_THRESHOLD:-1000}"
DUCKLAKE_BUFFER_SIZE_THRESHOLD_MB="${DUCKLAKE_BUFFER_SIZE_THRESHOLD_MB:-64}"
DUCKLAKE_BUFFER_MAX_MEMORY_MB="${DUCKLAKE_BUFFER_MAX_MEMORY_MB:-256}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Main Script
# ============================================================================

echo ""
echo "🔧 Generating WADM Manifest from Template"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Configuration:"
echo "  Template:          ${TEMPLATE_FILE}"
echo "  Output:            ${OUTPUT_FILE}"
echo "  Environment:       ${ENVIRONMENT}"
echo "  Version:           ${MANIFEST_VERSION}"
echo "  Actor Registry:    ${ACTOR_REGISTRY}"
echo "  Actor Tag:         ${ACTOR_TAG}"
echo "  Provider Registry: ${PROVIDER_REGISTRY}"
echo "  Provider Tag:      ${PROVIDER_TAG}"
echo "  DuckLake Tag:      ${DUCKLAKE_WRITE_TAG}"
echo "  Transfers Tag:     ${ETH_TRANSFERS_PROCESSOR_TAG}"
echo "  Router Tag:        ${NOTIFICATION_ROUTER_TAG}"
echo "  Redis URL:         ${REDIS_URL}"
echo "  NATS URL:          ${NATS_URL}"
echo "  Resend API Key:    ${RESEND_API_KEY:+set}"
echo "  Telegram Port:     ${TELEGRAM_WEBHOOK_PORT}"
echo "  Newheads Enabled:  ${NEWHEADS_ENABLED}"
echo "  S3 Endpoint:       ${S3_ENDPOINT}"
echo "  S3 Bucket:         ${S3_BUCKET}"
echo "  S3 Access Key:     ${S3_ACCESS_KEY_ID}"
echo "  PostgreSQL Host:   ${POSTGRES_HOST}:${POSTGRES_PORT}"
echo "  PostgreSQL User:   ${POSTGRES_USER}"
echo "  DuckLake DB:       ${DUCKLAKE_POSTGRES_DATABASE}"
echo "  DuckLake Buffer:   time=${DUCKLAKE_BUFFER_TIME_THRESHOLD_SECONDS}s count=${DUCKLAKE_BUFFER_COUNT_THRESHOLD} size=${DUCKLAKE_BUFFER_SIZE_THRESHOLD_MB}MB max_mem=${DUCKLAKE_BUFFER_MAX_MEMORY_MB}MB"
echo ""

# Check if template exists
if [ ! -f "$TEMPLATE_FILE" ]; then
    echo -e "${YELLOW}❌ Template file not found: ${TEMPLATE_FILE}${NC}"
    exit 1
fi

# Create output directory if needed
mkdir -p "$(dirname "$OUTPUT_FILE")"

# Generate manifest by substituting variables
echo -e "${BLUE}ℹ️  Generating manifest...${NC}"

# Use envsubst if available, otherwise use sed
if command -v envsubst &> /dev/null; then
    # Export variables for envsubst
    export ENVIRONMENT
    export MANIFEST_VERSION
    export ACTOR_REGISTRY
    export ACTOR_TAG
    export PROVIDER_REGISTRY
    export PROVIDER_TAG
    export DUCKLAKE_WRITE_TAG
    export ETH_TRANSFERS_PROCESSOR_TAG
    export NOTIFICATION_ROUTER_TAG
    export REDIS_URL
    export NATS_URL
    export RESEND_API_KEY
    export TELEGRAM_WEBHOOK_PORT
    export NEWHEADS_ENABLED
    export S3_ENDPOINT
    export S3_BUCKET
    export S3_ACCESS_KEY_ID
    export S3_SECRET_ACCESS_KEY
    export POSTGRES_HOST
    export POSTGRES_PORT
    export POSTGRES_USER
    export POSTGRES_PASSWORD
    export DUCKLAKE_POSTGRES_DATABASE
    export DUCKLAKE_BUFFER_TIME_THRESHOLD_SECONDS
    export DUCKLAKE_BUFFER_COUNT_THRESHOLD
    export DUCKLAKE_BUFFER_SIZE_THRESHOLD_MB
    export DUCKLAKE_BUFFER_MAX_MEMORY_MB

    envsubst < "$TEMPLATE_FILE" > "$OUTPUT_FILE"
else
    # Fallback to sed if envsubst not available
    sed -e "s|\${ENVIRONMENT}|${ENVIRONMENT}|g" \
        -e "s|\${MANIFEST_VERSION}|${MANIFEST_VERSION}|g" \
        -e "s|\${ACTOR_REGISTRY}|${ACTOR_REGISTRY}|g" \
        -e "s|\${ACTOR_TAG}|${ACTOR_TAG}|g" \
        -e "s|\${PROVIDER_REGISTRY}|${PROVIDER_REGISTRY}|g" \
        -e "s|\${PROVIDER_TAG}|${PROVIDER_TAG}|g" \
        -e "s|\${DUCKLAKE_WRITE_TAG}|${DUCKLAKE_WRITE_TAG}|g" \
        -e "s|\${ETH_TRANSFERS_PROCESSOR_TAG}|${ETH_TRANSFERS_PROCESSOR_TAG}|g" \
        -e "s|\${NOTIFICATION_ROUTER_TAG}|${NOTIFICATION_ROUTER_TAG}|g" \
        -e "s|\${REDIS_URL}|${REDIS_URL}|g" \
        -e "s|\${NATS_URL}|${NATS_URL}|g" \
        -e "s|\${NEWHEADS_ENABLED}|${NEWHEADS_ENABLED}|g" \
        -e "s|\${S3_ENDPOINT}|${S3_ENDPOINT}|g" \
        -e "s|\${S3_BUCKET}|${S3_BUCKET}|g" \
        -e "s|\${S3_ACCESS_KEY_ID}|${S3_ACCESS_KEY_ID}|g" \
        -e "s|\${S3_SECRET_ACCESS_KEY}|${S3_SECRET_ACCESS_KEY}|g" \
        -e "s|\${POSTGRES_HOST}|${POSTGRES_HOST}|g" \
        -e "s|\${POSTGRES_PORT}|${POSTGRES_PORT}|g" \
        -e "s|\${POSTGRES_USER}|${POSTGRES_USER}|g" \
        -e "s|\${POSTGRES_PASSWORD}|${POSTGRES_PASSWORD}|g" \
        -e "s|\${DUCKLAKE_POSTGRES_DATABASE}|${DUCKLAKE_POSTGRES_DATABASE}|g" \
        -e "s|\${DUCKLAKE_BUFFER_TIME_THRESHOLD_SECONDS}|${DUCKLAKE_BUFFER_TIME_THRESHOLD_SECONDS}|g" \
        -e "s|\${DUCKLAKE_BUFFER_COUNT_THRESHOLD}|${DUCKLAKE_BUFFER_COUNT_THRESHOLD}|g" \
        -e "s|\${DUCKLAKE_BUFFER_SIZE_THRESHOLD_MB}|${DUCKLAKE_BUFFER_SIZE_THRESHOLD_MB}|g" \
        -e "s|\${DUCKLAKE_BUFFER_MAX_MEMORY_MB}|${DUCKLAKE_BUFFER_MAX_MEMORY_MB}|g" \
        "$TEMPLATE_FILE" > "$OUTPUT_FILE"
fi

echo -e "${GREEN}✅ Manifest generated successfully${NC}"
echo ""
echo "Generated manifest: ${OUTPUT_FILE}"
echo ""
echo "To deploy this manifest:"
echo "  wash app put ${OUTPUT_FILE}"
echo "  wash app deploy ekko-platform ${MANIFEST_VERSION}"
echo ""
