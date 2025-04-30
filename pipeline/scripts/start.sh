#!/bin/bash
set -e

# Wait for Pulsar to be ready
echo "Waiting for Pulsar..."
until nc -z ${PULSAR_HOST:-pulsar} ${PULSAR_PORT:-6650}; do
    echo "Pulsar is unavailable - sleeping"
    sleep 2
done
echo "Pulsar is up"

# Wait for Redis if using Redis cache
if [ "$CACHE_TYPE" = "redis" ]; then
    echo "Waiting for Redis..."
    until nc -z ${REDIS_HOST:-redis} ${REDIS_PORT:-6379}; do
        echo "Redis is unavailable - sleeping"
        sleep 2
    done
    echo "Redis is up"
fi

# Start the pipeline
echo "Starting Ekko Pipeline..."
exec /app/pipeline
