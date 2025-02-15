# Use Bento as base image
FROM ghcr.io/warpstreamlabs/bento:latest

# Set working directory
WORKDIR /app

# Copy your Benthos configuration
COPY config.yaml /app/config.yaml

# The entrypoint is already set in the base image
# Default command if none provided
CMD ["-c", "/app/config.yaml"]
