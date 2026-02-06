#!/bin/bash
# NATS JetStream Configuration Setup for Ekko Notification System
# This script sets up the required NATS streams and subjects for notification delivery

set -e

NATS_HOST="${NATS_HOST:-localhost}"
NATS_PORT="${NATS_PORT:-4222}"
NATS_URL="nats://$NATS_HOST:$NATS_PORT"

echo "Setting up NATS JetStream configuration for Ekko notification system..."
echo "NATS URL: $NATS_URL"

# Wait for NATS to be ready
echo "Waiting for NATS to be ready..."
until nats --server="$NATS_URL" server ping 2>/dev/null; do
    echo "Waiting for NATS server at $NATS_URL..."
    sleep 2
done

echo "NATS server is ready. Creating streams..."

# Create notification streams for each channel
declare -a channels=("email" "slack" "sms" "telegram" "discord" "webhook" "websocket")

for channel in "${channels[@]}"; do
    echo "Creating stream for $channel notifications..."
    
    # Create stream for each notification channel
    nats --server="$NATS_URL" stream add "notifications-$channel" \
        --subjects "notifications.$channel.>" \
        --storage file \
        --retention workqueue \
        --discard old \
        --max-msgs 100000 \
        --max-bytes 10GB \
        --max-age 24h \
        --replicas 1 \
        --ack \
        --max-msg-size 1MB || echo "Stream notifications-$channel already exists"
done

# Create status reporting stream
echo "Creating notification status stream..."
nats --server="$NATS_URL" stream add "notification-status" \
    --subjects "notifications.status.>" \
    --storage file \
    --retention limits \
    --discard old \
    --max-msgs 500000 \
    --max-bytes 5GB \
    --max-age 168h \
    --replicas 1 \
    --ack \
    --max-msg-size 512KB || echo "Stream notification-status already exists"

# Create dead letter queue stream
echo "Creating dead letter queue stream..."
nats --server="$NATS_URL" stream add "notification-dlq" \
    --subjects "notifications.dlq.>" \
    --storage file \
    --retention limits \
    --discard old \
    --max-msgs 50000 \
    --max-bytes 1GB \
    --max-age 720h \
    --replicas 1 \
    --ack \
    --max-msg-size 1MB || echo "Stream notification-dlq already exists"

# Create metrics and monitoring stream
echo "Creating metrics stream..."
nats --server="$NATS_URL" stream add "notification-metrics" \
    --subjects "notifications.metrics.>" \
    --storage file \
    --retention limits \
    --discard old \
    --max-msgs 1000000 \
    --max-bytes 2GB \
    --max-age 168h \
    --replicas 1 \
    --ack \
    --max-msg-size 256KB || echo "Stream notification-metrics already exists"

echo "NATS JetStream setup completed successfully!"
echo ""
echo "Created streams:"
for channel in "${channels[@]}"; do
    echo "  - notifications-$channel: Subject pattern 'notifications.$channel.>'"
done
echo "  - notification-status: Subject pattern 'notifications.status.>'"
echo "  - notification-dlq: Subject pattern 'notifications.dlq.>'"
echo "  - notification-metrics: Subject pattern 'notifications.metrics.>'"
echo ""
echo "Stream information:"
nats --server="$NATS_URL" stream list