# Build stage
FROM golang:1.23-bullseye AS builder

WORKDIR /build

# Install build dependencies for DuckDB (requires C++ compiler and libraries)
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    libc6-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy go.mod and go.sum first for better caching
COPY go.mod go.sum ./

# Download dependencies with CGO enabled
RUN CGO_ENABLED=1 go mod download

# Copy source code
COPY . .

# Build without using the vendor directory
RUN rm -rf vendor && go mod tidy

# Build the application with CGO enabled for DuckDB
# Note: Remove GOOS/GOARCH to use native compilation in container
RUN CGO_ENABLED=1 \
    go build -mod=mod -ldflags="-w -s" -o pipeline ./cmd/ekko-pipeline

# Final stage (Debian-based runtime)
FROM debian:bullseye-slim

# Create non-root user
RUN groupadd -r ekko && useradd -r -g ekko ekko

WORKDIR /app

# Install runtime dependencies for DuckDB
RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    bash \
    ca-certificates \
    tzdata \
    libc6 \
    libgcc-s1 \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# Copy binary from builder and set permissions
COPY --from=builder /build/pipeline /app/
RUN chown ekko:ekko /app/pipeline && \
    chmod 500 /app/pipeline

# Copy start script and set permissions
COPY scripts/start.sh /app/
RUN chown ekko:ekko /app/start.sh && \
    chmod 500 /app/start.sh

# Switch to non-root user
USER ekko

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD nc -z localhost ${METRICS_PORT:-9090} || exit 1

# Run start script
ENTRYPOINT ["/app/start.sh"]
