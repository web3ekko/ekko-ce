#!/bin/bash
set -e

# Wait for NATS to be ready
echo "Waiting for NATS..."
# Extract host and port from NATS_URL
NATS_HOST=${NATS_HOST:-nats}
NATS_PORT=${NATS_PORT:-4222}

# If NATS_URL is provided, parse it to get host and port
if [ ! -z "${NATS_URL}" ]; then
    # Remove protocol prefix
    NATS_URL_CLEAN=${NATS_URL#nats://}
    # Extract host and port
    NATS_HOST=${NATS_URL_CLEAN%:*}
    NATS_PORT=${NATS_URL_CLEAN#*:}
    # If port is not in URL, use default
    if [ "$NATS_HOST" = "$NATS_PORT" ]; then
        NATS_PORT=4222
    fi
fi

until nc -z ${NATS_HOST} ${NATS_PORT}; do
    echo "NATS is unavailable - sleeping"
    sleep 2
done
echo "NATS is up"

# Wait for Redis if using Redis cache
if [ "$CACHE_TYPE" = "redis" ]; then
    echo "Waiting for Redis..."
    until nc -z ${REDIS_HOST:-redis} ${REDIS_PORT:-6379}; do
        echo "Redis is unavailable - sleeping"
        sleep 2
    done
    echo "Redis is up"
fi

# Print environment variables for debugging
echo "Environment variables:"
echo "PULSAR_URL=${PULSAR_URL}"
echo "PULSAR_ADMIN_URL=${PULSAR_ADMIN_URL}"
echo "NATS_URL=${NATS_URL}"

# Explicitly unset any Pulsar-related variables
unset PULSAR_URL
unset PULSAR_ADMIN_URL

# Start the pipeline
echo "Starting Ekko Pipeline..."
exec /app/pipeline
